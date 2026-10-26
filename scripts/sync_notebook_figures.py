"""Render marked TikZ diagrams and embed them in the tutorial notebook."""

from __future__ import annotations

import base64
from pathlib import Path
import re
import subprocess
import tempfile

import nbformat


ROOT = Path(__file__).resolve().parents[1]

PREAMBLE = r'''\documentclass[border=4pt]{standalone}
\usepackage[T1]{fontenc}
\usepackage[default]{sourcesanspro}
\usepackage{inconsolata}
\usepackage{xcolor,tikz}
\usetikzlibrary{arrows.meta,positioning}
\definecolor{ink}{HTML}{183247}
\definecolor{muted}{HTML}{526471}
\definecolor{accent}{HTML}{007D86}
\definecolor{pale}{HTML}{EAF5F4}
\definecolor{papergray}{HTML}{F3F5F7}
\definecolor{linegray}{HTML}{D5DEE4}
\begin{document}\color{ink}
'''


def main():
    source = (ROOT / 'jupyterlab_student_guide.tex').read_text()
    figures = dict(re.findall(
        r'% notebook-figure: (\w+)\s*(\\begin\{tikzpicture\}.*?\\end\{tikzpicture\})',
        source,
        re.S,
    ))
    notebook_path = ROOT / 'jupyterlab_tutorial.ipynb'
    notebook = nbformat.read(notebook_path, as_version=4)
    (ROOT / 'assets').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='jupyter-tutorial-figures-') as temporary:
        working = Path(temporary)
        for name in ('interface', 'upload'):
            figure = working / f'{name}.tex'
            figure.write_text(PREAMBLE + figures[name] + '\n\\end{document}\n')
            result = subprocess.run(
                ['pdflatex', '-interaction=nonstopmode', '-halt-on-error',
                 f'-output-directory={working}', str(figure)],
                capture_output=True,
                text=True,
            )
            if result.returncode:
                raise RuntimeError(result.stdout[-5000:])
            subprocess.run(
                ['pdftocairo', '-png', '-singlefile', '-r', '170',
                 str(working / f'{name}.pdf'), str(ROOT / 'assets' / name)],
                check=True,
            )
            filename = f'{name}.png'
            encoded = base64.b64encode((ROOT / 'assets' / filename).read_bytes()).decode('ascii')
            for cell in notebook.cells:
                if f'attachment:{filename}' in cell.source:
                    cell.setdefault('attachments', {})[filename] = {'image/png': encoded}
                    break
            else:
                raise ValueError(f'No notebook attachment reference found for {filename}')
            print(f'Updated {filename}', flush=True)
    nbformat.validate(notebook)
    nbformat.write(notebook, notebook_path)


if __name__ == '__main__':
    main()
