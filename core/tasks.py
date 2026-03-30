#!/usr/bin/env python3
"""
Exécution de fonctions dans un QgsTask (thread pool QGIS).
La fonction ne doit pas manipuler l'interface Qt ni QgsVectorLayer / QgsProject.
"""


def run_in_worker_thread(description, fn):
    """
    Exécute fn() dans un worker QgsTask et retourne son résultat.
    Si QGIS n'est pas disponible ou si le gestionnaire de tâches n'est pas utilisable,
    exécute fn() de façon synchrone sur le thread courant.
    """
    try:
        from qgis.core import QgsApplication, QgsTask
        from qgis.PyQt.QtCore import QEventLoop
    except ImportError:
        return fn()

    app = QgsApplication.instance()
    if app is None:
        return fn()

    result_box = []
    exc_box = []

    class _WorkerTask(QgsTask):
        def run(self):
            try:
                result_box.append(fn())
                return True
            except Exception as e:
                exc_box.append(e)
                return False

    task = _WorkerTask(description)
    loop = QEventLoop()

    def _finish():
        loop.quit()

    task.taskCompleted.connect(_finish)
    app.taskManager().addTask(task)
    loop.exec_()

    if exc_box:
        raise exc_box[0]
    return result_box[0] if result_box else None
