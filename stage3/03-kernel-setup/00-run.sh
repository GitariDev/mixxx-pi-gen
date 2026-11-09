# Keep the performance governor without the unsupported dynamic-preemption switch.
# Re-running the stage must not accumulate command-line options.
on_chroot <<'EOF'
    python3 - <<'PYTHON'
from pathlib import Path
path = Path('/boot/firmware/cmdline.txt')
options = [option for option in path.read_text().split()
           if option != 'preempt=full'
           and not option.startswith('cpufreq.default_governor=')]
options.append('cpufreq.default_governor=performance')
path.write_text(' '.join(options) + '\n')
PYTHON
EOF
