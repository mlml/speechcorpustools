

from PyQt5 import QtGui, QtCore, QtWidgets

class ResultsView(QtWidgets.QTableView):
    viewRequested = QtCore.pyqtSignal(str, float, float)
    def __init__(self, parent = None):
        super(ResultsView, self).__init__(parent)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showMenu)

        self.verticalHeader().hide()
        self.setSortingEnabled(True)

        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        self.clip = QtWidgets.QApplication.clipboard()

        self.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)

    def keyPressEvent(self, e):
        if (e.modifiers() & QtCore.Qt.ControlModifier) and e.key() == QtCore.Qt.Key_C:
            selected = self.selectionModel().selectedRows()
            s = ''

            for r in selected:
                for c in range(self.model().columnCount()):
                    ind = self.model().index(r.row(),c)
                    s += self.model().data(ind, QtCore.Qt.DisplayRole) + "\t"
                s = s[:-1] + "\n" #eliminate last '\t'
            self.clip.setText(s)
        else:
            super(ResultsView, self).keyPressEvent(e)

    def setModel(self,model):
        super(ResultsView, self).setModel(model)

    def mouseDoubleClickEvent(self, event):
        print ('hello')
        pos = event.pos()
        index = self.indexAt(pos)
        if index is None:
            return
        self.requestView(index)

    def requestView(self, index):
        index = self.model().mapToSource(index)
        times = self.model().sourceModel().times(index)
        discourse = self.model().sourceModel().discourse(index)
        self.viewRequested.emit(discourse, *times)

    def showMenu(self, pos):
        menu = QtWidgets.QMenu()
        index = self.indexAt(pos)
        viewAction = QtWidgets.QAction('View annotation', self)
        viewAction.triggered.connect(lambda : self.requestView(index))
        menu.addAction(viewAction)
        action = menu.exec_(self.viewport().mapToGlobal(pos))

    def selectNext(self):
        selected = self.selectionModel().selectedRows()
        if len(selected):
            current = selected[-1].row()
        else:
            current = 0

        if current + 1 == self.model().sourceModel().rowCount():
            return
        index = self.model().index(current + 1,0)
        self.selectionModel().select(index,
                QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows)
        self.requestView(index)

    def selectPrevious(self):
        selected = self.selectionModel().selectedRows()
        if len(selected):
            current = selected[0].row()
        else:
            current = 0
        if current == 0:
            return
        index = self.model().index(current - 1,0)
        self.selectionModel().select(index,
                QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows)
        self.requestView(index)
