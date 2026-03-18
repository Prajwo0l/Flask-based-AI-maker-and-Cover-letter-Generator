# 📄 AI-Powered Resume & Cover Letter Generator

A Flask-based web application that leverages a **fine-tuned large language model** (via PEFT + LoRA) to generate professional cover letters and resumes. The application also includes an ATS scoring engine, skill gap analysis, and multiple downloadable resume templates.

---

## 🚀 Features

| Feature | Description |
|---|---|
| **Cover Letter Generation** | AI-generated cover letters powered by a locally fine-tuned causal language model |
| **Resume Builder** | Create polished resumes with auto-generated summaries |
| **ATS Scorer** | Analyze resume–job description alignment with an ATS compatibility score |
| **Skill Gap Analyzer** | Identify missing skills between your resume and a target job description |
| **Resume Enhancer** | Upload an existing resume and a JD to receive optimization suggestions |
| **Multiple Templates** | Download resumes in PDF or DOCX format across Minimal, Formal, and Modern styles |
| **User Authentication** | Register/Login system with session management backed by SQLite |

---

## 🧠 Model Details

The cover letter generation engine is powered by a **causal language model fine-tuned using PEFT (Parameter-Efficient Fine-Tuning) with LoRA (Low-Rank Adaptation)**. The fine-tuned model is stored locally and loaded at runtime.

- **Fine-tuning technique:** LoRA via PEFT
- **Inference framework:** Hugging Face `transformers`
- **Device support:** CUDA (GPU) with automatic CPU fallback
- **Generation parameters:** `temperature=0.7`, `top_k=50`, `top_p=0.95`, `max_new_tokens=400`
- **Model path:** `./fine_tuned_model/`

> ⚠️ Ensure the `fine_tuned_model/` directory is present before starting the application. The model is loaded lazily on the first cover letter generation request.

---

## 🗂️ Project Structure

```
Flask-based-AI-maker-and-Cover-letter-Generator/
│
├── app.py                        # Flask application factory & entry point
├── routes.py                     # All route definitions (Blueprints)
├── requirements.txt              # Python dependencies
│
├── appe/                         # Core application logic
│   ├── cover_letter_generator.py # Model loading & letter generation
│   ├── resume_parser.py          # Extract & parse resume content
│   ├── job_desc_parser.py        # Extract text from job descriptions
│   ├── skill_analyzer.py         # Skill gap detection
│   ├── ats_scorer.py             # ATS compatibility scoring
│   ├── resume_summarizer.py      # Section-level resume summaries
│   ├── resume_optimizer.py       # Resume improvement suggestions
│   ├── logic.py                  # Summary generation & resume parsing
│   ├── templates.py              # PDF/DOCX resume template rendering
│   ├── models.py                 # SQLAlchemy User model
│   └── skill_db_relax_20.json    # Skill taxonomy database
│
├── fine_tuned_model/             # Local fine-tuned LLM (PEFT + LoRA)
├── templates/                    # Jinja2 HTML templates
├── static/                       # CSS, JS, and static assets
├── uploads/                      # Temporary file storage for uploads
└── instance/                     # SQLite database instance
```

---

## ⚙️ Installation & Setup

### Prerequisites

- Python 3.9 or higher
- `pip` package manager
- (Optional but recommended) NVIDIA GPU with CUDA for faster inference

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/Flask-based-AI-maker-and-Cover-letter-Generator.git
cd Flask-based-AI-maker-and-Cover-letter-Generator
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Additional dependencies you may need to install:

```bash
pip install torch torchvision torchaudio         # PyTorch (CUDA version recommended)
pip install transformers peft                    # Hugging Face + PEFT/LoRA
pip install flask flask-sqlalchemy werkzeug
pip install reportlab python-docx PyPDF2
pip install spacy scikit-learn sentence-transformers
python -m spacy download en_core_web_sm          # spaCy English model
```

### 4. Add the Fine-Tuned Model

Place your fine-tuned model files inside the `fine_tuned_model/` directory. This directory should contain:

```
fine_tuned_model/
├── config.json
├── tokenizer_config.json
├── tokenizer.json
├── special_tokens_map.json
├── adapter_config.json          # LoRA adapter config (if using PEFT adapter)
└── pytorch_model.bin / model.safetensors
```

### 5. Run the Application

```bash
python app.py
```

The application will be available at: **http://127.0.0.1:5000**

---

## 📋 Usage Guide

### Cover Letter Generation
1. Log in to your account
2. Navigate to **Cover Letter Generator**
3. Fill in your name, job title, target company, experience, and skills
4. Select a template style: `Minimal`, `Formal`, or `Modern`
5. Click **Generate** — the AI model will produce a tailored cover letter
6. Download as PDF in any template style

### Resume Builder
1. Navigate to **Create Resume**
2. Fill in your personal details, experience, education, skills, and projects
3. An AI-generated professional summary is automatically created
4. Preview the resume and download as **PDF** or **DOCX**

### Resume Enhancer (ATS + Skill Gap)
1. Navigate to **Resume Enhancer**
2. Upload your existing resume (PDF/DOCX) and a job description (PDF/DOCX/TXT)
3. Choose an action:
   - **ATS Score** — get a compatibility score with detailed feedback
   - **Summarize** — view section-level summaries highlighting skill matches
   - **Parse** — preview extracted text from both documents

---

## 🔐 Authentication

- Users can **register** with name, email, and password
- Sessions are managed server-side using Flask's `session`
- All generation and download routes are protected — login is required

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Flask, Flask-SQLAlchemy |
| **AI / ML** | Hugging Face Transformers, PEFT, LoRA, PyTorch |
| **NLP** | spaCy, scikit-learn, sentence-transformers |
| **PDF Generation** | ReportLab, python-docx |
| **Resume Parsing** | PyPDF2, python-docx |
| **Database** | SQLite (via SQLAlchemy ORM) |
| **Frontend** | Jinja2, HTML/CSS/JS |

---

## 🧪 Model Fine-Tuning Overview

The cover letter generation model was fine-tuned using **LoRA (Low-Rank Adaptation)** via the `peft` library on a dataset of structured cover letter prompts and outputs.

```
Base Model  →  LoRA Adapters (PEFT)  →  Fine-Tuned Model
                  ↓
         Frozen base weights +
         Trainable low-rank matrices (r, alpha)
```

This approach significantly reduces the number of trainable parameters compared to full fine-tuning, allowing efficient training even on consumer-grade hardware.

---

## 📌 Environment Notes

- The app runs in **debug mode** by default on `127.0.0.1:5000`. Change this for production deployment.
- Uploaded files are stored temporarily in `uploads/` and deleted after processing.
- GPU memory is explicitly cleared after each generation to prevent VRAM accumulation.
- The secret key in `app.py` should be replaced with a strong, randomly generated key before deploying.

---

## 📄 License

This project is intended for educational and personal use. Refer to the individual library licenses for third-party components.

---

## 🙋 Author

**Lamic**
Built with Flask, fine-tuned transformers, and a lot of ☕.
