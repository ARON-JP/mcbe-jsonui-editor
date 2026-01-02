import sys
import os
import json5

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog,
    QWidget, QHBoxLayout,
    QPlainTextEdit, QMessageBox,
    QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsPixmapItem, QGraphicsTextItem,
    QToolBar
)
from PySide6.QtGui import QAction, QPixmap, QPen, QColor, QPainter
from PySide6.QtCore import Qt

# =====================================
# 設定
# =====================================
RESOURCE_PACK_ROOT = "./resource_pack"
TEXTURE_ROOT = os.path.join(RESOURCE_PACK_ROOT, "textures")
SCENE_WIDTH = 1920
SCENE_HEIGHT = 1080

# =====================================
# Anchor 解決
# =====================================
def resolve_anchor(anchor, scene_w, scene_h, w, h):
    table = {
        "top_left": (0, 0),
        "top_middle": (scene_w // 2 - w // 2, 0),
        "top_right": (scene_w - w, 0),

        "left_middle": (0, scene_h // 2 - h // 2),
        "center": (scene_w // 2 - w // 2, scene_h // 2 - h // 2),
        "right_middle": (scene_w - w, scene_h // 2 - h // 2),

        "bottom_left": (0, scene_h - h),
        "bottom_middle": (scene_w // 2 - w // 2, scene_h - h),
        "bottom_right": (scene_w - w, scene_h - h),
    }
    return table.get(anchor, (0, 0))

def resolve_anchor_pair(anchor_from, anchor_to, scene_w, scene_h, w, h):
    # anchor_fromはアイテムサイズで、anchor_toはシーンサイズで計算
    x_to, y_to = resolve_anchor(anchor_to, scene_w, scene_h, w, h)
    dx, dy = resolve_anchor(anchor_from, w, h, w, h)
    return x_to - dx, y_to - dy

def parse_size(size):
    w, h = 100, 40
    if isinstance(size, list) and len(size) == 2:
        try:
            w_str = str(size[0])
            if "%c" in w_str:
                w = int(SCENE_WIDTH * float(w_str.replace("%c",""))/100)
            elif "%" in w_str:
                w = int(SCENE_WIDTH * float(w_str.replace("%",""))/100)
            else:
                w = int(float(w_str))
        except:
            pass
        try:
            h_str = str(size[1])
            if "%c" in h_str:
                h = int(SCENE_HEIGHT * float(h_str.replace("%c",""))/100)
            elif "%" in h_str:
                h = int(SCENE_HEIGHT * float(h_str.replace("%",""))/100)
            else:
                h = int(float(h_str))
        except:
            pass
    return [w, h]

def parse_offset(offset):
    if isinstance(offset, list) and len(offset) == 2:
        try:
            x = int(float(str(offset[0]).replace("px","")))
        except:
            x = 0
        try:
            y = int(float(str(offset[1]).replace("px","")))
        except:
            y = 0
        return [x, y]
    return [0, 0]

# =====================================
# UI Item
# =====================================
class UiItem(QGraphicsRectItem):
    def __init__(self, key, data, sync_callback, editor=None):
        self.key = key
        self.data = data
        self.sync_callback = sync_callback
        self.editor = editor

        size = parse_size(data.get("size", [100, 40]))
        self.data["size"] = size
        super().__init__(0, 0, size[0], size[1])

        self.setFlags(
            QGraphicsRectItem.ItemIsMovable |
            QGraphicsRectItem.ItemIsSelectable |
            QGraphicsRectItem.ItemSendsGeometryChanges
        )

        self.setPen(QPen(QColor(0, 255, 255), 2))
        self.setBrush(QColor(0, 255, 255, 50))

        self.child = None
        self.update_position()
        self.update_visual()

    def update_position(self):
        size = self.data.get("size", [100, 40])
        offset = parse_offset(self.data.get("offset", [0, 0]))
        anchor_to = self.data.get("anchor_to", "top_left")
        anchor_from = self.data.get("anchor_from", "top_left")

        base_x, base_y = resolve_anchor_pair(anchor_from, anchor_to, SCENE_WIDTH, SCENE_HEIGHT, size[0], size[1])
        self.setPos(base_x + offset[0], base_y + offset[1])

    def resolve_texture(self, texture):
        if texture.endswith(".png"):
            return os.path.join(TEXTURE_ROOT, texture)
        return os.path.join(TEXTURE_ROOT, texture + ".png")

    def update_visual(self):
        if self.child:
            self.child.setParentItem(None)
            self.child = None

        texture = self.data.get("texture")
        if texture:
            path = self.resolve_texture(texture)
            if os.path.exists(path):
                pixmap = QPixmap(path).scaled(
                    self.rect().width(),
                    self.rect().height(),
                    Qt.IgnoreAspectRatio,
                    Qt.SmoothTransformation
                )
                self.child = QGraphicsPixmapItem(pixmap, self)
                return

        # 画像がなければテキスト表示
        text = QGraphicsTextItem(f"#{self.key}", self)
        text.setDefaultTextColor(Qt.red)
        # テキストをアイテムサイズにフィットさせる
        text_width = text.boundingRect().width()
        text_height = text.boundingRect().height()
        scale_x = self.rect().width() / max(text_width, 1)
        scale_y = self.rect().height() / max(text_height, 1)
        text.setScale(min(scale_x, scale_y) * 0.8)  # 少し余白
        text.setPos(0, 0)
        self.child = text

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.ItemPositionChange:
            size = self.data.get("size", [100, 40])
            anchor_to = self.data.get("anchor_to", "top_left")
            anchor_from = self.data.get("anchor_from", "top_left")
            base_x, base_y = resolve_anchor_pair(anchor_from, anchor_to, SCENE_WIDTH, SCENE_HEIGHT, size[0], size[1])
            self.data["offset"] = [int(value.x() - base_x), int(value.y() - base_y)]
            self.sync_callback()
            if self.editor:
                self.scroll_to_key()
        return super().itemChange(change, value)

    def scroll_to_key(self):
        if not self.editor:
            return
        text = self.editor.toPlainText()
        index = text.find(f'"{self.key}"')
        if index != -1:
            cursor = self.editor.textCursor()
            cursor.setPosition(index)
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()

# =====================================
# 再帰的 controls 展開
# =====================================
def load_controls_recursively(parent_scene, controls, sync_callback, editor=None, parent_item=None):
    if isinstance(controls, dict):
        for key, val in controls.items():
            if isinstance(val, dict) and "type" in val:
                val["size"] = parse_size(val.get("size", [100, 40]))
                item = UiItem(key, val, sync_callback, editor)
                if parent_item:
                    item.setParentItem(parent_item)  # 階層表示
                parent_scene.addItem(item)
                if "controls" in val:
                    load_controls_recursively(parent_scene, val["controls"], sync_callback, editor, item)
    elif isinstance(controls, list):
        for entry in controls:
            load_controls_recursively(parent_scene, entry, sync_callback, editor, parent_item)

# =====================================
# Preview
# =====================================
class PreviewView(QGraphicsView):
    def __init__(self, sync_callback, editor=None):
        super().__init__()
        self.scene = QGraphicsScene(0, 0, SCENE_WIDTH, SCENE_HEIGHT)
        self.setScene(self.scene)
        self.sync_callback = sync_callback
        self.editor = editor
        self.setRenderHints(self.renderHints() | QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

    def load_jsonui(self, data):
        self.scene.clear()
        if "controls" in data:
            load_controls_recursively(self.scene, data["controls"], self.sync_callback, self.editor)
        for key, val in data.items():
            if key != "controls" and isinstance(val, dict) and "type" in val:
                val["size"] = parse_size(val.get("size", [100, 40]))
                item = UiItem(key, val, self.sync_callback, self.editor)
                self.scene.addItem(item)
        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

# =====================================
# Main Window
# =====================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Minecraft JsonUI Editor")
        self.resize(1600, 900)

        self.data = {}
        self.block_editor = False
        self.current_path = None

        # Editor + Preview
        self.editor = QPlainTextEdit()
        self.preview = PreviewView(self.sync_to_editor, self.editor)
        self.editor.textChanged.connect(self.sync_from_editor)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.addWidget(self.preview, 3)
        layout.addWidget(self.editor, 2)
        self.setCentralWidget(central)

        # Toolbar
        self.create_toolbar()

    def create_toolbar(self):
        toolbar = QToolBar("File")
        self.addToolBar(toolbar)

        open_action = QAction("Open", self)
        open_action.triggered.connect(self.open_jsonui)
        toolbar.addAction(open_action)

        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_file)
        toolbar.addAction(save_action)

        save_as_action = QAction("Save As", self)
        save_as_action.triggered.connect(self.save_file_as)
        toolbar.addAction(save_as_action)

    def open_jsonui(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open JsonUI", "", "JsonUI (*.json *.jsonc *.json5)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                self.data = json5.load(f)
            self.current_path = path
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))
            return

        self.preview.load_jsonui(self.data)
        self.sync_to_editor()

    def sync_to_editor(self):
        self.block_editor = True
        self.editor.setPlainText(json5.dumps(self.data, indent=2))
        self.block_editor = False

    def sync_from_editor(self):
        if self.block_editor:
            return
        try:
            self.data = json5.loads(self.editor.toPlainText())
            self.preview.load_jsonui(self.data)
        except Exception as e:
            print("Editor parse error:", e)

    def save_file(self):
        if not self.current_path:
            self.save_file_as()
            return
        try:
            with open(self.current_path, "w", encoding="utf-8") as f:
                json5.dump(self.data, f, indent=2)
            QMessageBox.information(self, "Saved", f"Saved to {self.current_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def save_file_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save As", "", "JsonUI (*.json *.jsonc *.json5)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json5.dump(self.data, f, indent=2)
                self.current_path = path
                QMessageBox.information(self, "Saved", f"Saved to {path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", str(e))

# =====================================
# Entry Point
# =====================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
