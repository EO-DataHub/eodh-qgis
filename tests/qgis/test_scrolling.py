"""Real wheel events stay bounded over expanded cards on Qt 5 and Qt 6."""

from unittest.mock import Mock

import pytest
from qgis.PyQt import QtCore, QtGui, QtTest, QtWidgets

from eodh_qgis.gui.hub_cards import CardList, ResultCard, WorkspaceCard
from eodh_qgis.gui.hub_scroll import ScrollComboBox, SmoothScrollArea


def wheel(widget, angle=-120, pixels=0):
    position = QtCore.QPointF(10, 10)
    event = QtGui.QWheelEvent(
        position,
        QtCore.QPointF(widget.mapToGlobal(QtCore.QPoint(10, 10))),
        QtCore.QPoint(0, pixels),
        QtCore.QPoint(0, angle),
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        QtCore.Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QtWidgets.QApplication.sendEvent(widget, event)


record = {
    "id": "fixture",
    "collection": "fixture",
    "_provider": "Airbus",
    "properties": {"order:status": "succeeded"},
    "assets": {f"asset{i}": {"href": f"https://example.test/{i}.tif", "type": "image/tiff"} for i in range(40)},
}


@pytest.mark.parametrize("card_class", [ResultCard, WorkspaceCard])
def test_expanded_asset_scrolling(qgis_app, card_class):
    dock = Mock(bbox=None)
    view = CardList()
    view.resize(500, 400)
    cards = [card_class(dock, dict(record, id=str(i))) for i in range(10)]
    for card in cards:
        view.add_card(card)
    view.show()
    qgis_app.processEvents()
    bar = view.verticalScrollBar()
    wheel(view.viewport())
    QtTest.QTest.qWait(190)
    collapsed_step = bar.value()
    assert 0 < collapsed_step <= 96, collapsed_step
    bar.setValue(0)
    cards[0].expand.click()
    qgis_app.processEvents()
    assert cards[0].height() > view.viewport().height()
    wheel(cards[0].assets.boxes[0][0])
    QtTest.QTest.qWait(190)
    assert bar.value() == collapsed_step, (bar.value(), collapsed_step)
    # High-resolution trackpad input remains pixel precise.
    before = bar.value()
    wheel(view.viewport(), angle=0, pixels=-7)
    assert bar.value() - before == 7
    # A second wheel event extends the animation rather than losing input.
    before = bar.value()
    wheel(view.viewport())
    wheel(view.viewport())
    QtTest.QTest.qWait(190)
    assert bar.value() - before == 2 * collapsed_step
    # Expanding a card above the viewport preserves the visible row and offset.
    bar.setValue(view.visualItemRect(view.item(3)).top() + bar.value() + 5)
    anchor = view.indexAt(QtCore.QPoint(0, 0))
    before = view.visualRect(anchor).top()
    cards[1].expand.click()
    qgis_app.processEvents()
    assert view.visualRect(anchor).top() == before
    # Selection changes inside an open card must not reposition the list.
    before = bar.value()
    cards[3].assets.boxes[0][0].click()
    qgis_app.processEvents()
    assert bar.value() == before
    view.close()


def test_nested_controls_and_horizontal_scrolling(qgis_app):
    area = SmoothScrollArea()
    area.resize(300, 300)
    content = QtWidgets.QWidget()
    content.setFixedSize(250, 1500)
    layout = QtWidgets.QVBoxLayout(content)
    combo = ScrollComboBox()
    combo.addItems([str(i) for i in range(50)])
    layout.addWidget(combo)
    layout.addStretch()
    area.setWidget(content)
    area.show()
    qgis_app.processEvents()
    wheel(combo)
    QtTest.QTest.qWait(190)
    assert combo.currentIndex() == 0
    assert area.verticalScrollBar().value() > 0
    # The horizontal thumbnail strip also accepts the ordinary mouse wheel.
    area.verticalScrollBar().setValue(0)
    content.setFixedSize(1500, 100)
    qgis_app.processEvents()
    wheel(area.viewport())
    QtTest.QTest.qWait(190)
    assert area.horizontalScrollBar().value() > 0
    area.close()
