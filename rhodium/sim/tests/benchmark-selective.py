#!/usr/bin/env python3
# Measures matched retained/expanded compilation and checked execution with reproducible artifacts.
# SPDX-License-Identifier: Apache-2.0
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    parser.add_argument('--repetitions', type=int, default=3)
    parser.add_argument('--cycles', type=int, default=1000000)
    parser.add_argument('--depths', type=int, nargs='+', default=[1, 3, 8])
    parser.add_argument('--cpu', type=int)
    parser.add_argument('--resume', action='store_true', help='reuse this validation batch\'s compiled root; write a new results subdirectory')
    args = parser.parse_args()
    if args.repetitions < 1 or args.cycles < 1 or any(d not in (1, 3, 8) for d in args.depths):
        parser.error('positive repetitions/cycles and validated depths 1, 3, or 8 required')
    if args.cpu is not None:
        os.sched_setaffinity(0, {args.cpu})
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    if args.resume:
        roots = list(directory.glob('compiled.*'))
        if len(roots) != 1 or not roots[0].is_dir():
            parser.error('--resume requires exactly one compiled root from this validation batch')
        compiled_root = str(roots[0])
        directory = Path(tempfile.mkdtemp(prefix='results.', dir=directory))
    else:
        compiled_root = tempfile.mkdtemp(prefix='compiled.', dir=directory)
    os.chdir(ROOT)
    scratch = directory / 'tmp'
    scratch.mkdir(exist_ok=True)
    env = dict(os.environ, TMPDIR=str(scratch), PYTHONDONTWRITEBYTECODE='1',
               PLTCOLLECTS=str(ROOT) + ':',
               PLTCOMPILEDROOTS=compiled_root)
    env.pop('RHODIUM_PRECOMPILED', None)
    env.pop('RDS_BENCH_BATCH', None)
    env['RDS_OPTIMIZER'] = subprocess.check_output(
        ['bash', 'rhodium/sim/compiler/run.sh', '--print-path'], cwd=ROOT, env=env, text=True).strip()
    cc = os.environ.get('CC', 'cc')
    flags = ['-std=c17', '-O2', '-Wall', '-Wextra', '-Werror']

    def measured(command, name, extra=None):
        command = list(map(str, command))
        start = time.perf_counter()
        with (directory / (name + '.log')).open('w') as log:
            pid = os.posix_spawnp(command[0], command, dict(env, **(extra or {})),
                                  file_actions=[(os.POSIX_SPAWN_DUP2, log.fileno(), 1),
                                                (os.POSIX_SPAWN_DUP2, log.fileno(), 2)])
            _, status, usage = os.wait4(pid, 0)
        if status:
            raise subprocess.CalledProcessError(os.waitstatus_to_exitcode(status), command)
        result = dict(wall_seconds=time.perf_counter() - start, peak_rss_kib=usage.ru_maxrss)
        (directory / (name + '.time.json')).write_text(json.dumps(result) + '\n')
        return result

    def cache_signature():
        return sorted((str(p.relative_to(compiled_root)), p.stat().st_size, p.stat().st_mtime_ns)
                      for p in Path(compiled_root).rglob('*') if p.is_file())

    # The first import can leave transitive dependencies to rebuild on later runs.
    # Require a complete direct/expanded pair without any bytecode writes.
    warmups = []
    if not args.resume:
        measured(['tools/run-racket-tests.sh', 'rhodium/sim/tests/benchmark-selective.rhm'], 'bytecode',
                 dict(RDS_BENCH_DEPTH='1', RDS_BENCH_OPTIONS='0', RDS_BENCH_MODE='direct',
                      RDS_BENCH_OUTPUT=str(directory / 'warmup.rds')))
    for attempt in range(8):
        before = cache_signature()
        for mode in ('direct', 'expanded'):
            warmups.append(measured(['racket', '-y', 'rhodium/sim/tests/benchmark-selective.rhm'],
                                    f'cache-warmup-{attempt}-{mode}',
                                    dict(RDS_BENCH_DEPTH='8', RDS_BENCH_OPTIONS='1', RDS_BENCH_MODE=mode,
                                         RDS_BENCH_OUTPUT=str(directory / 'warmup.rds'))))
        stable_cache = cache_signature()
        if stable_cache == before:
            break
    else:
        raise RuntimeError('bytecode did not stabilize; refusing incomparable startup/RSS measurements')
    runtime = directory / 'librhodium_sim.so'
    measured([cc, *flags, '-pthread', '-fPIC', '-shared',
              *sorted((ROOT / 'rhodium/sim/runtime').glob('*.c')), '-ldl', '-o', runtime], 'runtime-build')
    driver = directory / 'benchmark-selective'
    measured([cc, *flags, 'rhodium/sim/tests/benchmark-selective.c', '-L' + str(directory),
              '-lrhodium_sim', '-Wl,-rpath,' + str(directory), '-o', driver], 'driver-build')
    lowering_batches, phase_timings = {}, {}
    for repetition in range(args.repetitions):
        modes = ['direct', 'expanded'] if repetition % 2 == 0 else ['expanded', 'direct']
        for mode in modes:
            batch = f'lowering-{repetition}-{mode}'
            lowering_batches[batch] = measured(
                ['racket', '-y', 'rhodium/sim/tests/benchmark-selective.rhm'], batch,
                dict(RDS_BENCH_BATCH='1', RDS_BENCH_DEPTH=','.join(map(str, args.depths)),
                     RDS_BENCH_REPETITION=str(repetition), RDS_BENCH_MODE=mode,
                     RDS_BENCH_OUTPUT=str(directory)))
            assert cache_signature() == stable_cache, 'bytecode changed during measured emission'
            for line in (directory / (batch + '.log')).read_text().splitlines():
                name, *values = line.split()
                phase_timings[name] = (batch, *map(float, values))
            print(batch, 'emitted', flush=True)
    rows = []
    for depth in args.depths:
        for options in (0, 1):
            checksums = set()
            for repetition in range(args.repetitions):
                modes = ['direct', 'expanded'] if repetition % 2 == 0 else ['expanded', 'direct']
                for mode in modes:
                    name = f'{depth}-{options}-{repetition}-{mode}'
                    model = directory / (name + '.rds')
                    batch, elaboration_ms, lowering_ms, expansions = phase_timings[name]
                    assert expansions == (0 if mode == 'direct' else 1), (name, expansions)
                    source, binary = model.with_suffix('.c'), model.with_suffix('.so')
                    emission = measured([driver, model, 'emit', source, depth, options, args.cycles], name + '-emit')
                    compilation = measured([cc, *flags, '-shared', '-fPIC', source, '-o', binary], name + '-cc')
                    executions = {}
                    for engine, attachment in [('interpreter', '-'), ('compiled', binary)]:
                        # Warm code and caches in a separate, identically configured process.
                        measured([driver, model, 'run', attachment, depth, options, 10000], name + '-' + engine + '-warm')
                        execution = measured([driver, model, 'run', attachment, depth, options, args.cycles], name + '-' + engine)
                        seconds, checksum = (directory / (name + '-' + engine + '.log')).read_text().split()
                        checksums.add(checksum)
                        execution.update(checked_cycles_per_second=args.cycles / float(seconds),
                                         simulation_seconds=float(seconds), checksum=checksum)
                        executions[engine] = execution
                    rows.append(dict(depth=depth, pipe=bool(options), flow=bool(options), repetition=repetition,
                                     mode=mode, expansions=int(expansions), elaboration_ms=elaboration_ms,
                                     lowering_ms=lowering_ms, lowering_batch=batch, c_emission=emission,
                                     c_compilation=compilation, model_bytes=model.stat().st_size,
                                     c_bytes=source.stat().st_size, library_bytes=binary.stat().st_size,
                                     model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(), execution=executions))
                    print(name, 'passed', flush=True)
            assert len(checksums) == 1, (depth, options, checksums)
    summary = []
    for depth in args.depths:
        for options in (False, True):
            for mode in ('direct', 'expanded'):
                group = [r for r in rows if (r['depth'], r['pipe'], r['mode']) == (depth, options, mode)]
                summary.append(dict(depth=depth, pipe=options, flow=options, mode=mode,
                                    median_elaboration_ms=statistics.median(r['elaboration_ms'] for r in group),
                                    median_lowering_ms=statistics.median(r['lowering_ms'] for r in group),
                                    median_checked_compiled_cycles_per_second=statistics.median(
                                        r['execution']['compiled']['checked_cycles_per_second'] for r in group)))
    report = dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  dirty=subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True),
                  platform=platform.platform(), cpu_affinity=sorted(os.sched_getaffinity(0)),
                  compiler=subprocess.check_output([cc, '--version'], text=True).splitlines()[0],
                  racket=subprocess.check_output(['racket', '--version'], text=True).strip(),
                  rhombus_package=subprocess.check_output(['raco', 'pkg', 'show', 'rhombus'], env=env, text=True),
                  recorded_at=datetime.now(timezone.utc).isoformat(),
                  compiled_root=compiled_root, cache_warmups=warmups,
                  stable_cache_files=len(stable_cache),
                  benchmark_sources={name: hashlib.sha256((ROOT / 'rhodium/sim/tests' / name).read_bytes()).hexdigest()
                                     for name in ('benchmark-selective.py', 'benchmark-selective.rhm',
                                                  'benchmark-selective.c', 'selective-queue-fixture.rhdl')},
                  cpu_model=next((line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
                                  if line.startswith('model name')), platform.processor()),
                  flags=flags, cycles=args.cycles, seed=12648430, repetitions=args.repetitions,
                  note='Throughput includes host stimulus, independent oracle, and all pre/post-edge port reads. '
                       'Bytecode is warmed to stability; per-circuit timings exclude bytecode compilation. '
                       'Lowering peak RSS and process time cover each matched circuit batch; phase timings are per circuit. '
                       'Other peak RSS values are per subprocess; repeated rows expose variability.',
                  lowering_batches=lowering_batches, rows=rows, summary=summary)
    (directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Benchmark report:', directory / 'report.json', flush=True)


if __name__ == '__main__':
    main()
