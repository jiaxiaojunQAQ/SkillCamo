---
name: hpr-solver
description: Solve optimization & planning problems using natural language. Just describe what you need — fast, accurate, and built for AI agents.
---

# HPR Solver

Solve Linear Programming problems using HPR solver.

## Trigger

When user wants to solve an LP problem (MPS file or natural language description).

## Usage

### For MPS Files

User provides path to .mps file. Confirm parameters first:

```
⚠️ Please confirm parameters:
1. stoptol (default 1e-6): ?
2. time_limit (default 3600s): ?
3. device_number (0=GPU, -1=CPU): ?
4. Need variable values? (Yes/No)
```

After confirmation, run:

```bash
~/julia/julia-1.10.4/bin/julia --project ~/.openclaw/workspace/HPR-LP \
  ~/.openclaw/workspace/HPR-LP/hprlp_solve.jl <mps_file> <time_limit> <stoptol> <device>
```

### For Natural Language

1. Parse problem, output mathematical model for confirmation:

```markdown
📐 Mathematical Model:

```max
[objective function]
```

```s.t.
[constraint 1]
[constraint 2]
[constraint 3]
```

**Variables:**
- x₁ = [description]
- x₂ = [description]
```

2. After user confirms, ask parameters (same as MPS)

3. Model in Julia/JuMP:

```julia
using JuMP
using HPRLP

model = Model(HPRLP.Optimizer)
set_optimizer_attribute(model, "stoptol", <value>)
set_optimizer_attribute(model, "time_limit", <value>)
set_optimizer_attribute(model, "device_number", <value>)
set_optimizer_attribute(model, "verbose", true)

@variable(model, x1 >= 0)
@variable(model, x2 >= 0)

@constraint(model, c1, <constraint 1>)
@constraint(model, c2, <constraint 2>)

@objective(model, Max, <objective>)

optimize!(model)
```

4. Output Solution Summary:

```
📊 HPR-LP Results

=== Solution Summary ===
Status: [OPTIMAL/INFEASIBLE/...]
Iterations: <count>
Solve Time: <seconds>
Primal Objective: <value>
Dual Objective: <value>
KKT Error: <error>

=== Variables ===
x₁ = <value>
x₂ = <value>
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| stoptol | 1e-6 | Stopping tolerance |
| time_limit | 3600 | Time limit (seconds) |
| device_number | 0 | GPU device (-1 for CPU) |

## Non-LP Problems

If problem is NOT linear (has integer vars, x², products, etc.), respond:

```
⚠️ HPR only supports Linear Programming (LP).

This appears to be:
- Integer/MILP (use GLPK, CBC, HiGHS)
- Non-linear (use Ipopt)
- Quadratic (use Gurob, CPLEX)
```

## Requirements

- Julia 1.10.4
- HPR-LP
- Linux/macOS/Windows
