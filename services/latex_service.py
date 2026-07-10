"""LaTeX service: render a structured resume into a PDF using a fixed LaTeX
layout (the Harshibar / jakeryang template) compiled with Tectonic.

The flow is:
  resume_data (structured JSON from the LLM)  ->  build_resume_tex()  ->  .tex
  .tex  ->  compile_resume_pdf()  ->  PDF bytes

User-supplied text is escaped for LaTeX, and a tiny inline markdown subset is
honored inside any field: **bold** -> \\textbf{...} and [text](url) ->
\\href{url}{\\myuline{text}}. This keeps the candidate's data from ever breaking
compilation (a stray %, &, $, _ etc. is escaped) while still allowing emphasis
and links the way the original template uses them.

NOTE on fonts: the upstream template uses `fontawesome5`, whose OTF loading
crashes Tectonic's XeTeX engine. We use the older `fontawesome` (v4) package
instead — same icons, Type1 fonts, no crash. v4 commands have no trailing `*`
(\\faPhone, not \\faPhone*).
"""
import os
import re
import shutil
import subprocess
import tempfile

from config import TECTONIC_BIN


# --- LaTeX escaping -------------------------------------------------------

# Order matters: backslash must be replaced first so the replacements we add
# (which themselves contain backslashes) aren't double-escaped.
_LATEX_SPECIALS = [
    ("\\", r"\textbackslash{}"),
    ("&", r"\&"),
    ("%", r"\%"),
    ("$", r"\$"),
    ("#", r"\#"),
    ("_", r"\_"),
    ("{", r"\{"),
    ("}", r"\}"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
]


def latex_escape(text) -> str:
    """Escape a raw string so it is safe to drop into LaTeX as literal text."""
    s = "" if text is None else str(text)
    for char, repl in _LATEX_SPECIALS:
        s = s.replace(char, repl)
    return s


def _escape_url(url) -> str:
    """Escape the characters that break a URL inside \\href{...}."""
    s = "" if url is None else str(url)
    return (
        s.replace("\\", r"\textbackslash{}")
        .replace("%", r"\%")
        .replace("#", r"\#")
        .replace("&", r"\&")
        .replace("{", r"\{")
        .replace("}", r"\}")
    )


# Matches **bold** or [text](url). Used to convert a small markdown subset to
# LaTeX while escaping everything around it.
_INLINE = re.compile(r"\*\*(.+?)\*\*|\[([^\]]+)\]\(([^)]+)\)")


def md_inline_to_latex(text) -> str:
    """Convert **bold** and [text](url) to LaTeX; escape all other characters.

    Bold may itself contain a link (handled by recursion). Anything that isn't
    one of these two patterns is treated as literal text and escaped.
    """
    s = "" if text is None else str(text)
    out, pos = [], 0
    for m in _INLINE.finditer(s):
        out.append(latex_escape(s[pos:m.start()]))
        if m.group(1) is not None:                          # **bold**
            out.append(r"\textbf{" + md_inline_to_latex(m.group(1)) + "}")
        else:                                               # [text](url)
            text_part, url = m.group(2), m.group(3)
            out.append(
                r"\href{" + _escape_url(url) + r"}{\myuline{"
                + latex_escape(text_part) + "}}"
            )
        pos = m.end()
    out.append(latex_escape(s[pos:]))
    return "".join(out)


# --- Template -------------------------------------------------------------

# The document preamble + custom commands, verbatim from the Harshibar template
# except `fontawesome5` -> `fontawesome` (see module docstring). The body is
# assembled separately and inserted at %%BODY%%.
_PREAMBLE = r"""\documentclass[letterpaper,11pt]{article}

\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{verbatim}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}

% fontawesome v4 (v5 crashes Tectonic's XeTeX engine on OTF load)
\usepackage{fontawesome}

% fixed width
\usepackage[scale=0.90,lf]{FiraMono}

% greys
\definecolor{light-grey}{gray}{0.83}
\definecolor{dark-grey}{gray}{0.3}
\definecolor{text-grey}{gray}{.08}

\DeclareRobustCommand{\ebseries}{\fontseries{eb}\selectfont}
\DeclareTextFontCommand{\texteb}{\ebseries}

% custom underline
\usepackage{contour}
\usepackage[normalem]{ulem}
\renewcommand{\ULdepth}{1.8pt}
\contourlength{0.8pt}
\newcommand{\myuline}[1]{%
  \uline{\phantom{#1}}%
  \llap{\contour{white}{#1}}%
}

% helvetica-style sans-serif base font
\usepackage{tgheros}
\renewcommand*\familydefault{\sfdefault}
\usepackage[T1]{fontenc}

\pagestyle{fancy}
\fancyhf{}
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

% margins
\addtolength{\oddsidemargin}{-0.5in}
\addtolength{\evensidemargin}{0in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-.5in}
\addtolength{\textheight}{1.0in}

\urlstyle{same}
\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

\titleformat {\section}{
    \bfseries \vspace{2pt} \raggedright \large
}{}{0em}{}[\color{light-grey} {\titlerule[2pt]} \vspace{-4pt}]

\newcommand{\resumeItem}[1]{
  \item\small{
    {#1 \vspace{-1pt}}
  }
}

\newcommand{\resumeSubheading}[4]{
  \vspace{-1pt}\item
    \begin{tabular*}{\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & {\color{dark-grey}\small #2}\vspace{1pt}\\
      \textit{#3} & {\color{dark-grey} \small #4}\\
    \end{tabular*}\vspace{-4pt}
}

\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{\textwidth}{l@{\extracolsep{\fill}}r}
      #1 & {\color{dark-grey}#2} \\
    \end{tabular*}\vspace{-4pt}
}

\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}

\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{0pt}}

\color{text-grey}

\begin{document}
%%BODY%%
\end{document}
"""

# Map a contact "type" to its fontawesome v4 icon command.
_ICONS = {
    "phone": r"\faPhone",
    "email": r"\faEnvelope",
    "envelope": r"\faEnvelope",
    "github": r"\faGithub",
    "linkedin": r"\faLinkedin",
    "website": r"\faGlobe",
    "portfolio": r"\faGlobe",
    "globe": r"\faGlobe",
    "location": r"\faMapMarker",
    "mapmarker": r"\faMapMarker",
    "youtube": r"\faYoutube",
    "twitter": r"\faTwitter",
}


def _items(data, *keys):
    """Return the first present, list-valued field among `keys` (else [])."""
    for k in keys:
        v = data.get(k)
        if isinstance(v, list) and v:
            return v
    return []


def _bullet_block(bullets) -> str:
    """Render a list of bullet strings as a \\resumeItemListStart/End block.

    Returns "" when there are no bullets so we never emit an empty itemize
    (which LaTeX rejects).
    """
    items = [b for b in (bullets or []) if str(b).strip()]
    if not items:
        return ""
    lines = [r"      \resumeItemListStart"]
    lines += [r"        \resumeItem{" + md_inline_to_latex(b) + "}" for b in items]
    lines.append(r"      \resumeItemListEnd")
    return "\n".join(lines)


def _header(data) -> str:
    name = md_inline_to_latex(data.get("name") or "Your Name")
    contacts = data.get("contacts") or []
    pieces = []
    for c in contacts:
        if not isinstance(c, dict):
            continue
        text = (c.get("text") or "").strip()
        if not text:
            continue
        icon = _ICONS.get((c.get("type") or "").strip().lower(), "")
        label = r"\texttt{" + latex_escape(text) + "}"
        url = (c.get("url") or "").strip()
        if url:
            label = r"\href{" + _escape_url(url) + "}{" + label + "}"
        prefix = (icon + r" \hspace{2pt} ") if icon else ""
        pieces.append(prefix + label)
    sep = r" \hspace{1pt} $|$ \hspace{1pt} "
    contact_line = sep.join(pieces)

    # If there are no contacts to render, drop the empty contact_line + its
    # trailing \\ entirely — LaTeX errors with "There's no line here to end"
    # when \\ has nothing above it but whitespace. Just emit the centered name.
    if not contact_line:
        return (
            "\\begin{center}\n"
            "    \\textbf{\\Huge " + name + "}\n"
            "\\end{center}\n"
        )

    return (
        "\\begin{center}\n"
        "    \\textbf{\\Huge " + name + "} \\\\ \\vspace{5pt}\n"
        "    \\small " + contact_line + "\n"
        "    \\\\ \\vspace{-3pt}\n"
        "\\end{center}\n"
    )


def _experience_section(entries) -> str:
    if not entries:
        return ""
    out = ["\\section{EXPERIENCE}", r"  \resumeSubHeadingListStart"]
    for e in entries:
        out.append(
            r"    \resumeSubheading"
            + "{" + md_inline_to_latex(e.get("title") or e.get("organization") or "") + "}"
            + "{" + md_inline_to_latex(e.get("dates") or "") + "}"
            + "{" + md_inline_to_latex(e.get("role") or "") + "}"
            + "{" + md_inline_to_latex(e.get("location") or "") + "}"
        )
        block = _bullet_block(e.get("bullets"))
        if block:
            out.append(block)
    out.append(r"  \resumeSubHeadingListEnd")
    return "\n".join(out)


def _education_section(entries) -> str:
    if not entries:
        return ""
    out = ["\\section{EDUCATION}", r"  \resumeSubHeadingListStart"]
    for e in entries:
        out.append(
            r"    \resumeSubheading"
            + "{" + md_inline_to_latex(e.get("school") or e.get("institution") or "") + "}"
            + "{" + md_inline_to_latex(e.get("dates") or "") + "}"
            + "{" + md_inline_to_latex(e.get("degree") or "") + "}"
            + "{" + md_inline_to_latex(e.get("location") or "") + "}"
        )
        block = _bullet_block(e.get("bullets"))
        if block:
            out.append(block)
    out.append(r"  \resumeSubHeadingListEnd")
    return "\n".join(out)


def _projects_section(entries) -> str:
    if not entries:
        return ""
    out = ["\\section{PROJECTS}", r"    \resumeSubHeadingListStart"]
    for p in entries:
        name = md_inline_to_latex(p.get("name") or p.get("title") or "")
        out.append(
            r"      \resumeProjectHeading"
            + r"{\textbf{" + name + "}}"
            + "{" + md_inline_to_latex(p.get("dates") or "") + "}"
        )
        block = _bullet_block(p.get("bullets"))
        if block:
            out.append(block)
    out.append(r"    \resumeSubHeadingListEnd")
    return "\n".join(out)


def _skills_section(entries) -> str:
    if not entries:
        return ""
    rows = []
    for s in entries:
        category = (s.get("category") or "").strip()
        items = s.get("items")
        if isinstance(items, list):
            items = ", ".join(str(x) for x in items if str(x).strip())
        items = (items or "").strip()
        if not (category or items):
            continue
        rows.append(
            r"     \textbf{" + md_inline_to_latex(category) + "} "
            + "{: " + md_inline_to_latex(items) + "}"
        )
    if not rows:
        return ""
    body = " \\vspace{2pt} \\\\\n".join(rows)
    return (
        "\\section{SKILLS}\n"
        " \\begin{itemize}[leftmargin=0in, label={}]\n"
        "    \\small{\\item{\n"
        + body + "\n"
        "    }}\n"
        " \\end{itemize}"
    )


def build_resume_tex(resume_data: dict) -> str:
    """Assemble a full .tex document from structured resume_data."""
    data = resume_data or {}
    sections = [
        _header(data),
        _experience_section(_items(data, "experience", "experiences")),
        _projects_section(_items(data, "projects")),
        _education_section(_items(data, "education")),
        _skills_section(_items(data, "skills")),
    ]
    body = "\n\n".join(s for s in sections if s)
    return _PREAMBLE.replace("%%BODY%%", body)


# --- Compilation ----------------------------------------------------------

class LatexCompileError(RuntimeError):
    """Raised when Tectonic fails to produce a PDF."""


def compile_resume_pdf(resume_data: dict, timeout: int = 120) -> bytes:
    """Render resume_data to LaTeX, compile with Tectonic, return PDF bytes.

    Raises LatexCompileError on failure (missing engine, bad LaTeX, timeout),
    with a trimmed log to aid debugging.
    """
    if not (shutil.which(TECTONIC_BIN) or os.path.exists(TECTONIC_BIN)):
        raise LatexCompileError(
            f"Tectonic engine not found at '{TECTONIC_BIN}'. Set TECTONIC_BIN "
            "or place the binary at ./bin/tectonic."
        )

    tex = build_resume_tex(resume_data)
    with tempfile.TemporaryDirectory(prefix="resume_tex_") as workdir:
        tex_path = os.path.join(workdir, "resume.tex")
        pdf_path = os.path.join(workdir, "resume.pdf")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(tex)
        try:
            proc = subprocess.run(
                [TECTONIC_BIN, "-X", "compile", tex_path,
                 "--outfmt", "pdf", "--outdir", workdir],
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise LatexCompileError("LaTeX compilation timed out.")
        if proc.returncode != 0 or not os.path.exists(pdf_path):
            log = (proc.stderr or proc.stdout or "").strip()
            raise LatexCompileError(
                "LaTeX compilation failed:\n" + log[-1500:]
            )
        with open(pdf_path, "rb") as f:
            return f.read()
