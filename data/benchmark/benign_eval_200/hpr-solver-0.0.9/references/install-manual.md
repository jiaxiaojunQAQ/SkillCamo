# Manual Installation Guide

Follow these steps to set up HPR-LP Solver on your machine.

## Step 1: Install Julia 1.10.4

1. Download Julia 1.10.4 from: https://julialang.org/downloads/
   - Linux: julia-1.10.4-linux-x86_64.tar.gz
   - macOS: julia-1.10.4-mac64.tar.gz

2. Extract the downloaded archive to your home directory.

3. Verify installation by running:
   ```bash
   ~/julia-1.10.4/bin/julia --version
   ```

## Step 2: Get HPR-LP

1. Download HPR-LP from: https://github.com/PolyU-IOR/HPR-LP
   - Click the green "Code" button
   - Select "Download ZIP" or use Git

2. Place the files in: `~/.openclaw/workspace/HPR-LP/`

3. Open Julia and install dependencies:
   ```
   julia --project -e 'using Pkg; Pkg.instantiate()'
   ```

## Verify Installation

Run a simple test:
```bash
~/julia-1.10.4/bin/julia --project ~/.openclaw/workspace/HPR-LP \
  ~/.openclaw/workspace/HPR-LP/hprlp_solve.jl
```

## Paths Reference

After installation:
- Julia: `~/julia/julia-1.10.4/bin/julia`
- HPR-LP: `~/.openclaw/workspace/HPR-LP/`
- Solver script: `~/.openclaw/workspace/HPR-LP/hprlp_solve.jl`