import sys
from PyQt5 import QtGui, QtCore, QtWidgets

from polyglotdb import CorpusContext

from polyglotdb.graph.func import Sum, Count

from ..base import DetailedMessageBox

from ...models import QueryResultsModel, ProxyModel

from ...views import ResultsView

from ...workers import (QueryWorker, ExportQueryWorker)

from .graphical import GraphicalQuery

from .basic import BasicQuery

from .export import ExportProfileDialog

from ...profiles import (available_query_profiles, available_export_profiles,
                        QueryProfile, ExportProfile,
                        ensure_existence)

class QueryProfileWidget(QtWidgets.QWidget):
    profileSelected = QtCore.pyqtSignal(object)
    def __init__(self, parent = None):
        super(QueryProfileWidget, self).__init__(parent)
        self.querySelect = QtWidgets.QComboBox()
        self.refresh()

        self.querySelect.currentIndexChanged.connect(self.changeProfile)

        layout = QtWidgets.QFormLayout()
        layout.addRow('Query profiles', self.querySelect)
        self.setLayout(layout)

    def changeProfile(self):
        name = self.currentName()
        if name == '':
            return
        if name == 'New query':
            self.profileSelected.emit(QueryProfile())
        else:
            self.profileSelected.emit(QueryProfile.load_profile(name))

    def refresh(self):
        ensure_existence()
        self.querySelect.clear()
        self.querySelect.addItem('New query')
        profiles = available_query_profiles()
        for p in profiles:
            self.querySelect.addItem(p)

    def currentName(self):
        return self.querySelect.currentText()

    def select(self, name):
        self.querySelect.setCurrentIndex(self.querySelect.findText(name))

class ExportWidget(QtWidgets.QWidget):
    exportQuery = QtCore.pyqtSignal(object)
    def __init__(self, parent = None):
        super(ExportWidget, self).__init__(parent)

        layout = QtWidgets.QHBoxLayout()

        self.exportButton = QtWidgets.QToolButton()
        self.exportButton.setText('Export query results')
        self.exportButton.setPopupMode(QtWidgets.QToolButton.InstantPopup)

        self.refresh()
        layout.addWidget(self.exportButton)
        self.setLayout(layout)

    def beginExport(self, name):
        self.setDisabled(True)
        self.exportButton.setText('Exporting...')
        self.exportQuery.emit(name)

    def readyExport(self):
        self.setDisabled(False)
        self.exportButton.setText('Export query results')

    def refresh(self):
        self.readyExport()
        menu = QtWidgets.QMenu()
        newAction = QtWidgets.QAction('New export profile', self)
        newAction.triggered.connect(lambda x: self.beginExport('new'))
        menu.addAction(newAction)
        basicAction = QtWidgets.QAction('Basic columns', self)
        basicAction.triggered.connect(lambda x: self.beginExport('basic'))
        menu.addAction(basicAction)
        profiles = available_export_profiles()
        for p in profiles:
            act = QtWidgets.QAction(p, self)
            act.triggered.connect(lambda x: self.beginExport(p))
            menu.addAction(act)

        self.exportButton.setMenu(menu)

class SaveDialog(QtWidgets.QDialog):
    def __init__(self, default_name, parent = None):
        super(SaveDialog, self).__init__(parent)

        mainlayout = QtWidgets.QFormLayout()

        self.nameEdit = QtWidgets.QLineEdit()
        self.nameEdit.setText(default_name)

        mainlayout.addRow('Name', self.nameEdit)

        aclayout = QtWidgets.QHBoxLayout()

        self.acceptButton = QtWidgets.QPushButton('Save')
        self.acceptButton.setDefault(True)
        self.cancelButton = QtWidgets.QPushButton('Cancel')
        self.cancelButton.setAutoDefault(False)

        self.acceptButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)

        aclayout.addWidget(self.acceptButton)
        aclayout.addWidget(self.cancelButton)

        acwidget = QtWidgets.QWidget()
        acwidget.setLayout(aclayout)

        mainlayout.addWidget(acwidget)

        self.setLayout(mainlayout)


    def value(self):
        return self.nameEdit.text()

class QueryForm(QtWidgets.QWidget):
    finishedRunning = QtCore.pyqtSignal(object)
    def __init__(self):
        super(QueryForm, self).__init__()
        self.config = None

        mainLayout = QtWidgets.QVBoxLayout()
        headerLayout = QtWidgets.QHBoxLayout()

        self.queryWidget = BasicQuery()

        self.profileWidget = QueryProfileWidget()
        self.profileWidget.profileSelected.connect(self.queryWidget.updateProfile)

        self.executeButton = QtWidgets.QPushButton('Run query')
        self.exportWidget = ExportWidget()
        self.exportWidget.exportQuery.connect(self.exportQuery)

        self.saveButton = QtWidgets.QPushButton('Save query profile')
        self.executeButton.clicked.connect(self.runQuery)
        self.executeButton.setDisabled(True)

        self.saveButton.clicked.connect(self.saveProfile)
        self.saveButton.setDisabled(True)

        mainLayout.addWidget(self.profileWidget)
        mainLayout.addWidget(self.queryWidget)
        headerLayout.addWidget(self.executeButton)
        headerLayout.addWidget(self.exportWidget)
        headerLayout.addWidget(self.saveButton)
        mainLayout.addLayout(headerLayout)

        self.setLayout(mainLayout)

        self.queryWorker = QueryWorker()
        self.queryWorker.dataReady.connect(self.setResults)
        self.queryWorker.errorEncountered.connect(self.showError)

        self.exportWorker = ExportQueryWorker()
        self.exportWorker.errorEncountered.connect(self.showError)
        self.exportWorker.dataReady.connect(self.finishExport)

    def finishExport(self):
        self.exportWidget.refresh()


    def saveProfile(self):
        default = self.profileWidget.currentName()
        if default == 'New query':
            new_default_template = 'New query {}'
            index = 1
            while new_default_template.format(index) in available_query_profiles():
                index += 1
            default = new_default_template.format(index)

        dialog = SaveDialog(default, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            profile = self.currentProfile()
            profile.name = dialog.value()
            profile.save_profile()
            self.profileWidget.refresh()
            self.profileWidget.select(dialog.value())

    def currentProfile(self):
        return self.queryWidget.profile()

    def showError(self, e):
        reply = DetailedMessageBox()
        reply.setDetailedText(str(e))
        ret = reply.exec_()

    def exportQuery(self, profile_name):
        if self.config is None:
            return

        dialog = ExportProfileDialog(self.config, self.currentProfile().to_find, self)
        if profile_name != 'new':
            dialog.updateProfile(ExportProfile.load_profile(profile_name))
        if dialog.exec_() == QtWidgets.QDialog.Rejected:
            self.exportWidget.readyExport()
            return
        export_profile = dialog.profile()
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export data", filter = "CSV (*.txt  *.csv)")

        if not path:
            self.exportWidget.readyExport()
            return
        kwargs = {}
        kwargs['config'] = self.config
        kwargs['profile'] = self.currentProfile()
        kwargs['export_profile'] = export_profile
        kwargs['path'] = path
        self.exportWorker.setParams(kwargs)
        self.exportWorker.start()

    def runQuery(self):
        self.queryWorker.stop()
        if self.config is None:
            return
        kwargs = {}
        kwargs['config'] = self.config
        kwargs['profile'] = self.currentProfile()

        self.queryWorker.setParams(kwargs)
        self.queryWorker.start()

    def updateConfig(self, config):
        self.config = config
        if self.config is None or self.config.corpus_name == '':
            self.executeButton.setDisabled(True)
            self.exportWidget.setDisabled(True)
            self.saveButton.setDisabled(True)
            return
        self.executeButton.setDisabled(False)
        self.exportWidget.setDisabled(False)
        self.saveButton.setDisabled(False)
        with CorpusContext(config) as c:
            h = c.hierarchy
        self.queryWidget.setHierarchy(h)


    def setResults(self, results):
        self.finishedRunning.emit(results)

class QueryResults(QtWidgets.QWidget):
    def __init__(self, results):
        super(QueryResults, self).__init__()

        self.query = results[0]

        self.resultsModel = QueryResultsModel(results[1])

        self.tableWidget = ResultsView()

        self.proxyModel = ProxyModel()
        self.proxyModel.setSourceModel(self.resultsModel)
        self.proxyModel.setSortRole( QueryResultsModel.SortRole )
        self.proxyModel.setDynamicSortFilter(False)
        self.tableWidget.setModel(self.proxyModel)

        layout = QtWidgets.QVBoxLayout()

        layout.addWidget(self.tableWidget)

        self.setLayout(layout)

class QueryWidget(QtWidgets.QWidget):
    viewRequested = QtCore.pyqtSignal(str, float, float)
    def __init__(self):
        super(QueryWidget, self).__init__()
        self.config = None
        self.tabs = QtWidgets.QTabWidget()
        self.currentIndex = 1
        self.queryForm = QueryForm()
        self.queryForm.finishedRunning.connect(self.updateResults)

        self.tabs.addTab(self.queryForm, 'New query')

        layout = QtWidgets.QVBoxLayout()

        layout.addWidget(self.tabs)

        self.setLayout(layout)

    def updateConfig(self, config):
        self.config = config

        self.queryForm.updateConfig(config)

    def updateResults(self, results):
        name = 'Query {}'.format(self.currentIndex)
        self.currentIndex += 1
        widget = QueryResults(results)
        widget.tableWidget.viewRequested.connect(self.viewRequested.emit)
        self.tabs.addTab(widget, name)

    def markAnnotated(self, value):
        w = self.tabs.currentWidget()
        if not isinstance(w, QueryResults):
            return
        w.tableWidget.markAnnotated(value)

    def requestNext(self):
        w = self.tabs.currentWidget()
        if not isinstance(w, QueryResults):
            return
        w.tableWidget.selectNext()

    def requestPrevious(self):
        w = self.tabs.currentWidget()
        if not isinstance(w, QueryResults):
            return
        w.tableWidget.selectPrevious()
