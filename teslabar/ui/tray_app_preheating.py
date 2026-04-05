"""Preheating section for the system tray menu."""

import asyncio
import logging

from PySide6.QtWidgets import QMenu, QWidgetAction, QLabel
from PySide6.QtGui import Qt

from teslabar.services.tesla_api import TeslaService

logger = logging.getLogger(__name__)


class PreheatingSection:
    """Manages the preheating on/off label in the tray menu."""

    def __init__(self, menu: QMenu, tesla_service: TeslaService) -> None:
        self._tesla = tesla_service

        self._label = QLabel("Preheating: --")
        self._label.setTextFormat(Qt.TextFormat.RichText)
        self._label.setContentsMargins(20, 4, 20, 4)
        self._label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._label.mousePressEvent = self._on_click

        self._widget_action = QWidgetAction(menu)
        self._widget_action.setDefaultWidget(self._label)

    @property
    def widget_action(self) -> QWidgetAction:
        return self._widget_action

    def update(self, is_preconditioning: bool, enabled: bool) -> None:
        self._widget_action.setEnabled(enabled)
        if is_preconditioning:
            self._label.setText(
                "Preheating: <span style='color:red; font-weight:bold;'>ON</span>"
            )
        else:
            self._label.setText(
                "Preheating: <span style='color:green; font-weight:bold;'>OFF</span>"
            )

    def _on_click(self, event) -> None:
        if not self._widget_action.isEnabled():
            return
        if self._tesla.vehicle_data.is_preconditioning:
            logger.info("Turning preheating OFF")
            asyncio.ensure_future(self._tesla.preconditioning_off())
        else:
            logger.info("Turning preheating ON")
            asyncio.ensure_future(self._tesla.preconditioning_on())
