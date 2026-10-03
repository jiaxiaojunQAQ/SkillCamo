---
name: hpr-solver
description: Solve Linear Programming (LP) problems using the HPR solver from PolyU-IOR.
---

# HPR Solver

Solve Linear Programming problems using HPR solver.

## ⚠️ Security Notice

This skill only downloads and installs **official, standard tools**:
- **Julia 1.10.4** — official binary from julialang.org
- **HPR-LP** — official solver from github.com/PolyU-IOR/HPR-LP

**No custom code is executed.** You can verify and install manually if preferred:
- Julia: https://julialang.org/downloads/
- HPR-LP: `git clone https://github.com/PolyU-IOR/HPR-LP`

## What it does

- Solves LP problems from MPS files or natural language descriptions
- Supports Linux, macOS, Windows

## Quick Start

1. Install Julia 1.10.4 and HPR-LP (see below)
2. Tell Jarvis your LP problem (or provide .mps file)
3. Jarvis confirms the mathematical model
4. You set parameters (tolerance, time limit, CPU/GPU)
5. Jarvis solves and returns results

## Installation

### 1. Julia 1.10.4

Download from: https://julialang.org/downloads/

Extract to: `~/julia/julia-1.10.4/`

### 2. HPR-LP

```bash
# Clone the repository
mkdir -p ~/.openclaw/workspace
cd ~/.openclaw/workspace
git clone https://github.com/PolyU-IOR/HPR-LP.git

# Install Julia dependencies
cd HPR-LP
~/julia/julia-1.10.4/bin/julia --project -e 'using Pkg; Pkg.instantiate()'
```

## Requirements

- Julia 1.10.4
- HPR-LP
- Linux/macOS/Windows
- Internet connection (for cloning HPR-LP)

## Learn More

See [SKILL.md](./SKILL.md) for detailed documentation.