# SkillsBench

[![OpenReward Environment](https://img.shields.io/badge/%E2%AD%90%20OpenReward-Environment-f7e6cc)](https://openreward.ai/benchflow/skillsbench)

## Description

**SkillsBench** is a meta-environment for evaluating multi-step problem-solving capabilities of AI agents using diverse, real-world skill-based tasks. Tasks span engineering, science, finance, software development, and data processing domains, each running in an isolated Docker container with domain-specific tools and data. The original benchmark contains 84 tasks across 11 domains; this implementation includes 77 tasks.

This OpenReward implementation is ported from the [Harbor Framework](https://harborframework.com/) implementation originally made by [Xiangyi Li](https://github.com/xdotli).

## Capabilities

- Engineering calculations (3D STL parsing, CAD analysis, control systems)
- Scientific analysis (earthquake detection, exoplanet analysis, protein expression)
- Software development (bug fixes, code migrations, CVE patches)
- Data processing (TF-IDF search, financial modeling, spreadsheet operations)
- Multi-modal tasks (video processing, audio conversion, 3D rendering)
- Domain-specific skill application across diverse fields

## Compute Requirements

Agents are given a sandbox with 1 CPU and 2GB RAM by default. Each task runs in an isolated Docker container with task-specific tooling (Python, Node.js, Rust, etc.) and pre-loaded data files.

## License

[MIT](https://opensource.org/license/mit)

## Tasks

There is one split in this environment:

- **test**: 77 skill-based tasks (subset of 84 in original benchmark)

Example tasks include:
- **3d-scan-calc**: Calculate mass from 3D STL scan with material densities
- **adaptive-cruise-control**: Implement PID-based ACC from sensor data
- **earthquake-phase-association**: Seismic event detection and phase picking
- **fix-druid-loophole-cve**: Patch security vulnerability in Apache Druid
- **protein-expression-analysis**: Analyze gene expression data
- **video-filler-word-remover**: Process video to remove filler words
- **lean4-proof**: Complete formal mathematical proofs

Tasks include domain-specific skill definitions (markdown files) to help agents understand concepts like PID control, vehicle dynamics, or financial modeling.

## Reward Structure

This is a sparse, verifiable reward environment. Rewards are computed when the agent submits their answer:

- **1.0**: All test cases pass
- **0.0**: Any test case fails

No LLM grader is used. Each task has a custom pytest-based test suite that validates outputs against ground-truth calculations with appropriate tolerances.

## Data

Each task contains:
- `instruction.md`: Task description and requirements
- `task.toml`: Metadata (difficulty, category, timeouts, resource requirements)
- `environment/`: Task-specific data files (CSVs, STL files, YAML configs, etc.)
- `environment/skills/`: Domain knowledge documentation in markdown
- `tests/`: Pytest-based verification suite
- `solution/`: Reference solution script

## Tools

Agents have access to 5 tools:

- **bash**: Execute bash commands in the sandboxed container
- **view**: View file contents or directory listings (with optional line ranges)
- **str_replace**: Replace strings in files (must be unique occurrence)
- **create_file**: Create new files with specified content
- **submit_answer**: Run test suite and get reward

## Time Horizon

SkillsBench is a multi-turn environment where agents iteratively explore data, write code, test solutions, and refine before submission.

[Statistics on average tool calls here]

## Environment Difficulty

Benchmark results from the original paper (pass rate on 84 tasks):

| Agent | Without Skills | With Skills | Δ |
|-------|---------------|-------------|-----|
| Gemini CLI (Gemini 3 Flash) | 31.3% | 48.7% | +17.4 |
| Claude Code (Opus 4.5) | 22.0% | 45.3% | +23.3 |
| Codex (GPT-5.2) | 30.6% | 44.7% | +14.1 |
| Claude Code (Opus 4.6) | 30.6% | 44.5% | +13.9 |
| Gemini CLI (Gemini 3 Pro) | 27.6% | 41.2% | +13.6 |

Curated skills improve average pass rate by 16.2 percentage points, though effects vary widely by domain (+4.5pp for Software Engineering to +51.9pp for Healthcare).

## Other Environment Requirements

SkillsBench requires an OpenReward API key for sandbox access:

- **api_key**: Required in secrets parameter for OpenReward sandbox API

Some tasks may require additional API keys injected into the sandbox:
- `OPENAI_API_KEY`: For tasks using OpenAI API
- `ANTHROPIC_API_KEY`: For tasks using Claude API
- `GH_AUTH_TOKEN`: For GitHub-based tasks

Export and pass secrets:

```bash
export OPENAI_API_KEY=your_openai_api_key
export ANTHROPIC_API_KEY=your_anthropic_api_key
export GH_AUTH_TOKEN=your_gh_auth_token
```

```python
async with environment.session(task=task, secrets={"openai_api_key": OPENAI_API_KEY, "anthropic_api_key": ANTHROPIC_API_KEY, "gh_auth_token": GH_AUTH_TOKEN}) as session:
```

## Safety

SkillsBench tasks are run in isolated Docker containers. Tasks involve computational problem-solving and do not interact with external services beyond the sandbox.

## Citations

This environment implements the SkillsBench benchmark. If you use this environment, please cite the original paper:

```bibtex
@misc{li2026skillsbenchbenchmarkingagentskills,
      title={SkillsBench: Benchmarking How Well Agent Skills Work Across Diverse Tasks}, 
      author={Xiangyi Li and Wenbo Chen and Yimin Liu and Shenghan Zheng and Xiaokun Chen and Yifeng He and Yubo Li and Bingran You and Haotian Shen and Jiankai Sun and Shuyi Wang and Binxu Li and Qunhong Zeng and Di Wang and Xuandong Zhao and Yuanli Wang and Roey Ben Chaim and Zonglin Di and Yipeng Gao and Junwei He and Yizhuo He and Liqiang Jing and Luyang Kong and Xin Lan and Jiachen Li and Songlin Li and Yijiang Li and Yueqian Lin and Xinyi Liu and Xuanqing Liu and Haoran Lyu and Ze Ma and Bowei Wang and Runhui Wang and Tianyu Wang and Wengao Ye and Yue Zhang and Hanwen Xing and Yiqi Xue and Steven Dillmann and Han-chung Lee},
      year={2026},
      eprint={2602.12670},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2602.12670}, 
}
```
