.PHONY: all pdf check notebook-figures clean

all: jupyterlab_student_guide.pdf

pdf: jupyterlab_student_guide.pdf

jupyterlab_student_guide.pdf: jupyterlab_student_guide.tex
	latexmk -pdf -interaction=nonstopmode -halt-on-error $<

check:
	python3 scripts/validate_notebook.py

notebook-figures:
	python3 scripts/sync_notebook_figures.py

clean:
	latexmk -c jupyterlab_student_guide.tex
