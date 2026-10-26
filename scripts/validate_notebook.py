"""Run the teaching notebook in fresh kernels without changing its saved outputs."""

from __future__ import annotations

import base64
import copy
import os
from pathlib import Path
import re
import shutil
import tempfile

import nbformat
from nbclient import NotebookClient
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / 'jupyterlab_tutorial.ipynb'


def check_structure(notebook):
    nbformat.validate(notebook)
    assert len({cell.id for cell in notebook.cells}) == len(notebook.cells)
    for cell in notebook.cells:
        if cell.cell_type == 'code':
            assert cell.execution_count is None, f'{cell.id}: clear the saved execution count'
            assert not cell.outputs, f'{cell.id}: clear saved outputs before publishing'
        for filename in re.findall(r'attachment:([^\s)]+)', cell.source):
            attachment = base64.b64decode(cell.attachments[filename]['image/png'], validate=True)
            assert attachment == (ROOT / 'assets' / filename).read_bytes()
    assert 'Ready to use notebooks in your course?' not in '\n'.join(
        cell.source for cell in notebook.cells
    )
    markdown = '\n'.join(cell.source for cell in notebook.cells if cell.cell_type == 'markdown')
    anchors = set(re.findall(r'<a id="([^"]+)"', markdown))
    assert set(re.findall(r'\]\(#([^)]+)\)', markdown)) <= anchors


def execute_case(notebook, *, with_csv, completed):
    case_name = 'completed exercises' if completed else ('with CSV' if with_csv else 'without CSV')
    print(f'Executing {case_name} ...', flush=True)
    notebook = copy.deepcopy(notebook)
    if completed:
        for cell in notebook.cells:
            if cell.id == 'array-practice':
                cell.source = 'squared_values = values**2'
            elif cell.id == 'final-practice':
                cell.source = (
                    'practice_x = np.linspace(0, 1, 101)\n'
                    'practice_y = practice_x**2\n'
                    'practice_area = trapezoid(practice_y, x=practice_x)'
                )

    notebook.cells.append(nbformat.v4.new_code_cell(
        'assert x.shape == y.shape == (201,)\n'
        'assert abs(area - 2) < 5e-5\n'
        'assert Path("sine_curve.png").is_file()\n'
        'assert Path("sine_data.csv").is_file()\n',
        id='validation-only',
    ))

    with tempfile.TemporaryDirectory(prefix='jupyter-tutorial-') as temporary:
        working = Path(temporary)
        if with_csv:
            shutil.copy2(ROOT / 'measurements.csv', working / 'measurements.csv')
        environment = {
            **os.environ,
            'IPYTHONDIR': str(working / '.ipython'),
            'JUPYTER_CONFIG_DIR': str(working / '.jupyter'),
            'JUPYTER_RUNTIME_DIR': str(working / '.runtime'),
            'MPLCONFIGDIR': str(working / '.matplotlib'),
            'MPLBACKEND': 'module://matplotlib_inline.backend_inline',
        }
        client = NotebookClient(
            notebook,
            kernel_name='python3',
            timeout=120,
            record_timing=False,
            resources={'metadata': {'path': str(working)}},
        )
        executed = client.execute(env=environment)

        data = np.loadtxt(working / 'sine_data.csv', delimiter=',', skiprows=1)
        assert data.shape == (201, 2)
        np.testing.assert_allclose(data[:, 0], np.linspace(0, np.pi, 201))
        np.testing.assert_allclose(data[:, 1], np.sin(data[:, 0]))
        assert (working / 'sine_data.csv').read_text().splitlines()[0] == 'x,y'
        with Image.open(working / 'sine_curve.png') as image:
            image.verify()

        outputs = {
            cell.id: ''.join(output.get('text', '') for output in cell.get('outputs', []))
            for cell in executed.cells
        }
        if with_csv:
            assert 'Data shape: (5, 2)' in outputs['load-data']
        else:
            assert 'Upload measurements.csv' in outputs['load-data']
            assert not (working / 'measurements.csv').exists()
        if completed:
            assert 'Correct:' in outputs['array-practice-check']
            assert 'Correct:' in outputs['final-practice-check']
            assert 'Integral estimate: 0.333350' in outputs['final-practice-check']
        else:
            assert 'Enter your expression' in outputs['array-practice-check']
            assert 'Complete the three expressions' in outputs['final-practice-check']
        plot_cell = next(cell for cell in executed.cells if cell.id == 'sine-plot')
        assert any('image/png' in output.get('data', {}) for output in plot_cell.outputs)
    print(f'Passed: {case_name}', flush=True)


def check_incorrect_answers(notebook):
    cells = {cell.id: cell for cell in notebook.cells}
    cases = [
        ('array-practice-check', {'squared_values': np.array([1, 2, 3, 4])}),
        ('final-practice-check', {
            'practice_x': np.linspace(0, 1, 101),
            'practice_y': np.linspace(0, 1, 101)**2,
            'practice_area': 1 / 3,
        }),
    ]
    for cell_id, answers in cases:
        try:
            exec(compile(cells[cell_id].source, f'<{cell_id}>', 'exec'), {'np': np, **answers})
        except AssertionError:
            continue
        raise AssertionError(f'{cell_id} accepted an incorrect answer')
    print('Passed: incorrect answers are caught by the exercise checks', flush=True)


def main():
    before = NOTEBOOK.read_bytes()
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    check_structure(notebook)
    execute_case(notebook, with_csv=True, completed=False)
    execute_case(notebook, with_csv=False, completed=False)
    execute_case(notebook, with_csv=True, completed=True)
    check_incorrect_answers(notebook)
    assert NOTEBOOK.read_bytes() == before
    print('Notebook validated; distributed outputs remain empty.', flush=True)


if __name__ == '__main__':
    main()
