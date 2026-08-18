# Eval Harness – P8 Evaluation Framework

This directory contains the evaluation harness for the **GenAI Enterprise Knowledge Assistant**.

The harness reads a gold-standard Q&A dataset, sends each question to the `/chat` endpoint (or uses a mock backend), evaluates the returned answer and citations, and computes key retrieval and response-quality metrics.

---

## 📋 Quick Start

### 1. Install Dependencies

Install the required Python packages:

```bash
pip install aiohttp openai
```

If you are running the test suite, also install `pytest`:

```bash
pip install pytest
```

---

### 2. Run with Mock Mode

Mock mode allows you to test the evaluation harness without running the actual backend.

```bash
python eval/harness.py --gold eval/gold_qa.json --mock --output results.json
```

This is useful for verifying that the evaluation framework and its metrics are working correctly.

---

### 3. Run with the Real Backend

Start your GenAI Enterprise Knowledge Assistant backend first.

Then run:

```bash
python eval/harness.py \
    --gold eval/gold_qa.json \
    --api-url http://localhost:8000 \
    --output results.json
```

On Windows PowerShell, the same command can be written as:

```powershell
python eval/harness.py --gold eval/gold_qa.json --api-url http://localhost:8000 --output results.json
```

The harness will send requests to:

```text
http://localhost:8000/chat
```

---

### 4. Run with Faithfulness Evaluation

Faithfulness evaluation uses an LLM to determine whether the generated answer is actually supported by the retrieved citation chunks.

Set your OpenAI API key.

#### Windows PowerShell

```powershell
$env:OPENAI_API_KEY = "sk-..."
```

Then run:

```powershell
python eval/harness.py --gold eval/gold_qa.json --mock --output results.json --openai-key $env:OPENAI_API_KEY
```

#### Linux / macOS

```bash
export OPENAI_API_KEY="sk-..."
```

Then:

```bash
python eval/harness.py --gold eval/gold_qa.json --mock --output results.json --openai-key $OPENAI_API_KEY
```

> **Note:** Never commit your OpenAI API key to GitHub or include it directly in source code.

---

# 📊 What It Measures

The evaluation harness measures several important aspects of the knowledge assistant.

| Metric               | Description                                                                                        |
| -------------------- | -------------------------------------------------------------------------------------------------- |
| **Hit-Rate@k**       | Percentage of questions where the correct document appears within the top-k retrieved chunks.      |
| **MRR**              | Mean Reciprocal Rank. Measures how early the first correct chunk appears in the retrieval results. |
| **Refusal Accuracy** | Measures whether factual questions are answered and refusal questions are correctly refused.       |
| **Faithfulness**     | Measures whether generated answers are fully supported by the retrieved citation chunks.           |

---

## 1. Hit-Rate@k

Hit-Rate@k measures whether the expected document appears in the first `k` retrieved chunks.

For example:

```text
Top 5 retrieved chunks:

1. EHS Policy
2. Human Rights Policy
3. Code of Ethics
4. Supplier Standards
5. Whistleblower Policy
```

If the expected document is `Human Rights Policy`, then:

```text
Hit@5 = 1
```

If the expected document is not present in the top 5:

```text
Hit@5 = 0
```

The final Hit-Rate@5 is the percentage of questions for which this condition is satisfied.

---

## 2. Mean Reciprocal Rank (MRR)

MRR measures the position of the **first correct retrieved chunk**.

The reciprocal rank is calculated as:

```text
Reciprocal Rank = 1 / rank
```

Examples:

```text
Correct chunk at rank 1 → 1/1 = 1.00
Correct chunk at rank 2 → 1/2 = 0.50
Correct chunk at rank 3 → 1/3 = 0.33
Correct chunk at rank 5 → 1/5 = 0.20
```

The MRR is the average reciprocal rank across all questions.

A higher MRR indicates that relevant information is generally retrieved near the top of the results.

---

## 3. Refusal Accuracy

The dataset contains two types of questions:

```text
factual
refusal
```

For a **factual question**, the system is expected to provide an answer rather than refuse.

For a **refusal question**, the system is expected to refuse because the requested information should not be provided.

Therefore:

```text
Factual question + answer provided → Correct
Factual question + refusal → Incorrect

Refusal question + refusal → Correct
Refusal question + answer → Incorrect
```

This metric evaluates the assistant's ability to distinguish between questions that should be answered and questions that should be refused.

---

## 4. Faithfulness

Faithfulness evaluates whether the generated answer is supported by the retrieved document chunks.

For example, if the retrieved chunk says:

```text
The policy applies to all directors, officers, and employees.
```

and the generated answer says:

```text
The policy applies to all directors, officers, and employees.
```

the answer is supported by the retrieved evidence.

However, if the answer adds unsupported information such as:

```text
The policy applies to all directors, officers, employees,
contractors, customers, and external partners.
```

when the retrieved chunk does not mention these groups, the answer may be considered unfaithful.

Faithfulness evaluation requires an OpenAI API key.

---

# 📁 File Structure

The recommended directory structure is:

```text
eval/
├── gold_qa.json
├── harness.py
├── README.md
└── results.json
```

The test directory is:

```text
tests/
└── test_harness.py
```

After running the evaluation, `results.json` is generated automatically if the `--output` argument is provided.

---

# 🎯 Gold QA Dataset

The `gold_qa.json` file contains the gold-standard questions used to evaluate the assistant.

The dataset covers six policy documents:

| Document               | Factual | Refusal |   Total |
| ---------------------- | ------: | ------: | ------: |
| Human Rights Policy    |      33 |       0 |      33 |
| EHS Policy             |      31 |       0 |      31 |
| Supplier Standards     |      30 |      30 |      60 |
| Whistleblower Policy   |      30 |      30 |      60 |
| Anti-Corruption Policy |      30 |      30 |      60 |
| Code of Ethics         |      30 |      30 |      60 |
| **TOTAL**              | **184** | **120** | **304** |

> **Important:** The counts above add up to **304 questions**. If your actual `gold_qa.json` contains 335 questions, update the table and dataset breakdown to match the actual file.

---

## Gold QA Format

Each question contains the expected answer, source document, section, and expected response type.

Example:

```json
{
  "question": "Who does the Human Rights Policy apply to?",
  "answer": "All directors, officers, and employees...",
  "document_id": "human-rights-policy.pdf",
  "section_path": "Scope",
  "expected_response_type": "factual"
}
```

For a refusal question:

```json
{
  "question": "Example refusal question",
  "answer": "",
  "document_id": "supplier-standards.pdf",
  "section_path": "Restricted Information",
  "expected_response_type": "refusal"
}
```

The `expected_response_type` must be either:

```text
factual
```

or:

```text
refusal
```

---

# 🚀 Usage Examples

## Windows PowerShell

### Mock Mode

```powershell
python eval/harness.py --gold eval/gold_qa.json --mock --output results.json
```

### Real Backend

```powershell
python eval/harness.py --gold eval/gold_qa.json --api-url http://localhost:8000 --output results.json
```

### With OpenAI Faithfulness Evaluation

```powershell
$env:OPENAI_API_KEY = "sk-..."

python eval/harness.py --gold eval/gold_qa.json --mock --output results.json --openai-key $env:OPENAI_API_KEY
```

---

## Linux / macOS

### Mock Mode

```bash
python eval/harness.py --gold eval/gold_qa.json --mock --output results.json
```

### Real Backend

```bash
python eval/harness.py --gold eval/gold_qa.json --api-url http://localhost:8000 --output results.json
```

### With OpenAI Faithfulness Evaluation

```bash
export OPENAI_API_KEY="sk-..."

python eval/harness.py --gold eval/gold_qa.json --mock --output results.json --openai-key $OPENAI_API_KEY
```

---

# 📈 Sample Output

A typical evaluation summary looks like:

```text
============================================================
EVALUATION SUMMARY
============================================================
Total questions: 304
Errors: 0

Overall Metrics:
  hit_at_5: 0.8234
  hit_at_10: 0.8912
  mrr: 0.7456
  faithfulness_accuracy: 0.9100
  refusal_accuracy: 0.9500

Factual Questions:
  hit_at_5: 0.8500
  hit_at_10: 0.9100
  mrr: 0.7800
  faithfulness_accuracy: 0.9100
  refusal_accuracy: 0.9200

Refusal Questions:
  hit_at_5: 0.0000
  hit_at_10: 0.0000
  mrr: 0.0000
  faithfulness_accuracy: 0.0000
  refusal_accuracy: 0.9800
============================================================
```

> The numbers above are **sample values only**. Actual results depend on the backend, retrieval system, model, and gold dataset.

---

# 🧪 Running Tests

The evaluation harness includes automated tests.

First, make sure `pytest` is installed:

```bash
pip install pytest
```

Run all tests:

```bash
pytest tests/test_harness.py -v
```

Run a specific test:

```bash
pytest tests/test_harness.py::TestLoadGoldQuestions -v
```

Run the complete test directory:

```bash
pytest tests/ -v
```

A successful test run should show output similar to:

```text
============================= test session starts =============================
collected XX items

tests/test_harness.py::TestLoadGoldQuestions::test_load_questions PASSED
tests/test_harness.py::TestLoadGoldQuestions::test_question_structure PASSED
...

============================== XX passed ======================================
```

---

# 🔧 Command-Line Arguments

The harness supports the following arguments:

| Argument        | Required | Description                                           |
| --------------- | -------- | ----------------------------------------------------- |
| `--gold`        | ✅ Yes    | Path to `gold_qa.json`.                               |
| `--mock`        | ❌ No     | Use the mock API instead of the real backend.         |
| `--api-url`     | ❌ No     | Base URL of the `/chat` endpoint.                     |
| `--openai-key`  | ❌ No     | OpenAI API key used for faithfulness evaluation.      |
| `--output`      | ❌ No     | Path for the detailed JSON evaluation results.        |
| `--concurrency` | ❌ No     | Maximum number of concurrent requests. Default: `10`. |

### Example

```bash
python eval/harness.py \
    --gold eval/gold_qa.json \
    --api-url http://localhost:8000 \
    --output results.json \
    --concurrency 10
```

---

# 🔌 API Contract

When running against the real backend, the harness expects the `/chat` endpoint to return a JSON response with the following structure:

```json
{
  "answer": "string",
  "refused": false,
  "citations": [
    {
      "document_id": "string",
      "section_path": "string",
      "text": "string"
    }
  ],
  "confidence": 0.95,
  "conflict": {}
}
```

---

## API Response Fields

### `answer`

The generated answer returned by the knowledge assistant.

```json
"answer": "The policy applies to all employees."
```

---

### `refused`

Indicates whether the assistant refused to answer.

```json
"refused": false
```

For a refusal:

```json
"refused": true
```

---

### `citations`

Contains the document chunks used to generate the answer.

Each citation should contain:

```json
{
  "document_id": "human-rights-policy.pdf",
  "section_path": "Scope",
  "text": "Relevant document text..."
}
```

The harness uses this information for retrieval and faithfulness evaluation.

---

### `confidence`

Represents the confidence associated with the generated answer.

Example:

```json
"confidence": 0.95
```

---

### `conflict`

Contains information about conflicts detected between retrieved sources, if applicable.

Example:

```json
"conflict": {}
```

---

# ⚠️ Important Notes

## 1. UTF-8 BOM Handling

Some Windows tools save JSON files with a UTF-8 Byte Order Mark (BOM).

The harness handles this automatically by opening the gold dataset using:

```python
encoding="utf-8-sig"
```

Therefore, a `gold_qa.json` file containing a UTF-8 BOM should still load correctly.

---

## 2. API Contract Must Match

When using the real backend, make sure the `/chat` endpoint returns the fields expected by the harness:

```text
answer
refused
citations
confidence
conflict
```

If the response structure is different, the harness may report errors or fail to evaluate the response correctly.

---

## 3. Faithfulness Requires an OpenAI API Key

Faithfulness evaluation requires access to an OpenAI model.

Set:

```text
OPENAI_API_KEY
```

before running the faithfulness evaluation.

The configured evaluator uses:

```text
gpt-4o-mini
```

Make sure the API key has access to the required model.

---

## 4. Mock Mode Does Not Require the Backend

Use:

```bash
--mock
```

when you want to test the evaluation framework without running the actual knowledge assistant backend.

This is especially useful during development and CI testing.

---

## 5. Concurrency

The harness supports concurrent API requests to speed up evaluation.

The default is:

```text
10 concurrent requests
```

You can change it using:

```bash
--concurrency 20
```

For example:

```bash
python eval/harness.py \
    --gold eval/gold_qa.json \
    --api-url http://localhost:8000 \
    --concurrency 20
```

If the backend has limited resources, use a lower concurrency value.

---

# 🧪 Creating the Tests Folder

If the `tests` folder does not already exist, create it.

### Windows PowerShell

```powershell
mkdir tests -ErrorAction SilentlyContinue
```

Create the test file:

```powershell
New-Item -Path "tests/test_harness.py" -ItemType File
```

Open the file:

```powershell
notepad tests/test_harness.py
```

Paste the provided test code into the file and save it.

---

# 📂 Recommended Project Structure

The complete project can be organized as:

```text
project-root/
│
├── eval/
│   ├── gold_qa.json
│   ├── harness.py
│   ├── README.md
│   └── results.json
│
├── tests/
│   └── test_harness.py
│
├── app/
│   └── ...
│
├── requirements.txt
└── README.md
```

---

# 🔄 Typical Evaluation Workflow

The evaluation process follows these steps:

```text
                 ┌─────────────────┐
                 │   gold_qa.json  │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │   harness.py    │
                 └────────┬────────┘
                          │
                    Send Questions
                          │
              ┌───────────┴───────────┐
              │                       │
              ▼                       ▼
       ┌─────────────┐         ┌─────────────┐
       │ Mock Backend│         │ Real /chat  │
       └──────┬──────┘         └──────┬──────┘
              │                       │
              └───────────┬───────────┘
                          ▼
                 ┌─────────────────┐
                 │ Answers +       │
                 │ Citations       │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ Metric          │
                 │ Calculation     │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ results.json    │
                 └─────────────────┘
```

The main evaluation flow is:

1. Load the gold-standard questions.
2. Send each question to the mock or real `/chat` endpoint.
3. Collect the generated answer.
4. Collect refusal status.
5. Collect citations and retrieved chunks.
6. Compare retrieved documents against the expected document.
7. Calculate Hit-Rate@5 and Hit-Rate@10.
8. Calculate MRR.
9. Evaluate refusal accuracy.
10. Optionally evaluate faithfulness using an LLM.
11. Save detailed results to `results.json`.
12. Print the evaluation summary.

---

# 📄 Results File

When the following option is provided:

```bash
--output results.json
```

the harness writes detailed evaluation results to the specified JSON file.

Example:

```json
{
  "question": "Who does the Human Rights Policy apply to?",
  "expected_document": "human-rights-policy.pdf",
  "expected_response_type": "factual",
  "answer": "The policy applies to all directors, officers, and employees.",
  "refused": false,
  "citations": [],
  "hit_at_5": true,
  "hit_at_10": true,
  "rank": 1,
  "reciprocal_rank": 1.0,
  "faithful": true
}
```

The exact fields depend on the implementation of `harness.py`.

---

# 🛠️ Troubleshooting

## `ModuleNotFoundError: No module named 'aiohttp'`

Install the required dependency:

```bash
pip install aiohttp
```

---

## `ModuleNotFoundError: No module named 'openai'`

Install:

```bash
pip install openai
```

---

## `pytest` is not recognized

Install pytest:

```bash
pip install pytest
```

Then run:

```bash
python -m pytest tests/test_harness.py -v
```

---

## Backend Connection Error

If you see a connection error when using:

```bash
--api-url http://localhost:8000
```

make sure the backend is running.

You can first test the harness using:

```bash
python eval/harness.py --gold eval/gold_qa.json --mock --output results.json
```

If mock mode works but the real backend fails, check that:

```text
1. The backend is running.
2. Port 8000 is correct.
3. The /chat endpoint exists.
4. The API response matches the expected contract.
```

---

## Invalid JSON / BOM Error

If `gold_qa.json` was created using Windows tools and contains a UTF-8 BOM, the harness should handle it automatically using:

```python
encoding="utf-8-sig"
```

If the problem persists, validate the JSON file and make sure there are no trailing commas or malformed objects.

---

# 🎯 Evaluation Goals

The evaluation harness is designed to answer four important questions about the GenAI Enterprise Knowledge Assistant:

### 1. Does the system retrieve the correct information?

Measured using:

```text
Hit-Rate@5
Hit-Rate@10
MRR
```

### 2. Does the system answer when it should?

Measured using:

```text
Refusal Accuracy
```

### 3. Does the system refuse when it should?

Also measured using:

```text
Refusal Accuracy
```

### 4. Are generated answers grounded in retrieved evidence?

Measured using:

```text
Faithfulness
```

Together, these metrics provide a broader view of the assistant's retrieval and response quality.

---

# 📌 Recommended Evaluation Command

For a complete evaluation against the real backend:

```powershell
$env:OPENAI_API_KEY = "sk-..."

python eval/harness.py `
    --gold eval/gold_qa.json `
    --api-url http://localhost:8000 `
    --output results.json `
    --openai-key $env:OPENAI_API_KEY `
    --concurrency 10
```

For a quick local test without a backend:

```powershell
python eval/harness.py `
    --gold eval/gold_qa.json `
    --mock `
    --output results.json
```

---

# 📝 License

Part of the **GenAI Enterprise Knowledge Assistant** project.

---

# 🤝 Contact

**Owner:** P8

**Team:** All tags (P1–P8)

For questions, issues, or changes to the evaluation harness, reach out through the team channel.
