import sys
import os
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QPushButton, 
                            QVBoxLayout, QHBoxLayout, QWidget, QFileDialog, 
                            QMessageBox, QScrollArea)
from PyQt5.QtGui import QPixmap, QPainter, QPen, QImage, QColor
from PyQt5.QtCore import Qt, QPoint, QRect, QLine
from PIL import Image

class Rectangle:
    def __init__(self, start, end):
        self.start = start
        self.end = end
        
    def get_qrect(self):
        """Возвращает QRect для отрисовки прямоугольника"""
        return QRect(
            min(self.start.x(), self.end.x()),
            min(self.start.y(), self.end.y()),
            abs(self.start.x() - self.end.x()),
            abs(self.start.y() - self.end.y())
        )

class ImageCutterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        
        # Переменные для работы с изображением
        self.image_path = None
        self.original_pixmap = None
        self.display_pixmap = None
        self.rectangles = []
        self.drawing = False
        self.start_point = None
        self.current_point = None
        
    def init_ui(self):
        self.setWindowTitle('Разрезка сканированных изображений')
        self.setGeometry(100, 100, 1200, 800)
        
        # Создание главного виджета и компоновки
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # Виджет для прокрутки изображения
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        
        # Создание виджета для отображения изображения
        self.image_label = QLabel("Загрузите изображение")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(800, 600)
        self.image_label.mousePressEvent = self.mouse_press_event
        self.image_label.mouseMoveEvent = self.mouse_move_event
        self.image_label.mouseReleaseEvent = self.mouse_release_event
        self.image_label.paintEvent = self.paint_event
        
        self.scroll_area.setWidget(self.image_label)
        main_layout.addWidget(self.scroll_area)
        
        # Создание компоновки для кнопок
        button_layout = QHBoxLayout()
        
        # Кнопка для выбора файла
        self.btn_open = QPushButton("Открыть изображение")
        self.btn_open.clicked.connect(self.open_image)
        button_layout.addWidget(self.btn_open)
        
        # Кнопка для очистки выделений
        self.btn_clear = QPushButton("Очистить выделения")
        self.btn_clear.clicked.connect(self.clear_rectangles)
        button_layout.addWidget(self.btn_clear)
        
        # Кнопка для разрезки изображения
        self.btn_cut = QPushButton("Разрезать")
        self.btn_cut.clicked.connect(self.cut_image)
        button_layout.addWidget(self.btn_cut)
        
        main_layout.addLayout(button_layout)
        
        self.setCentralWidget(main_widget)
        
    def open_image(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self, "Выберите изображение", "", "Изображения (*.tif *.tiff)"
        )
        
        if file_path:
            try:
                self.image_path = file_path
                # Загружаем оригинальное изображение через PIL для поддержки TIFF
                pil_image = Image.open(file_path)
                # Конвертируем в RGB, если нужно
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')
                
                # Преобразуем для отображения с уменьшенным размером для предпросмотра
                # Максимальный размер для отображения
                max_width = 1000
                max_height = 800
                width, height = pil_image.size
                
                scale = min(max_width / width, max_height / height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                
                # Уменьшаем для предпросмотра
                pil_preview = pil_image.resize((new_width, new_height), Image.LANCZOS)
                
                # Конвертируем PIL изображение в QPixmap
                img = pil_preview.convert("RGBA")
                data = img.tobytes("raw", "RGBA")
                qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888)
                
                self.original_pixmap = QPixmap.fromImage(qimg)
                self.display_pixmap = self.original_pixmap.copy()
                
                # Устанавливаем изображение и размер метки
                self.image_label.setPixmap(self.display_pixmap)
                self.image_label.resize(self.display_pixmap.size())
                
                # Очищаем выделения
                self.rectangles = []
                
                # Устанавливаем размер виджета и обновляем интерфейс
                self.btn_clear.setEnabled(True)
                self.btn_cut.setEnabled(True)
                
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось открыть изображение: {str(e)}")
    
    def mouse_press_event(self, event):
        if self.display_pixmap and event.button() == Qt.LeftButton:
            self.drawing = True
            self.start_point = event.pos()
            self.current_point = event.pos()
    
    def mouse_move_event(self, event):
        if self.drawing:
            self.current_point = event.pos()
            self.image_label.update()
    
    def mouse_release_event(self, event):
        if self.drawing and event.button() == Qt.LeftButton:
            self.drawing = False
            # Добавляем прямоугольник только если его размер достаточно большой
            if (self.start_point - event.pos()).manhattanLength() > 10:
                self.rectangles.append(Rectangle(self.start_point, event.pos()))
            self.image_label.update()
    
    def paint_event(self, event):
        if self.display_pixmap:
            painter = QPainter(self.image_label)
            
            # Отрисовка изображения
            painter.drawPixmap(0, 0, self.display_pixmap)
            
            # Настройка пера для прямоугольников
            pen = QPen(Qt.red, 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.setBrush(QColor(255, 0, 0, 30))  # Полупрозрачная заливка
            
            # Отрисовка существующих прямоугольников
            for rect in self.rectangles:
                painter.drawRect(rect.get_qrect())
            
            # Отрисовка прямоугольника, который сейчас рисуется
            if self.drawing:
                current_rect = QRect(
                    min(self.start_point.x(), self.current_point.x()),
                    min(self.start_point.y(), self.current_point.y()),
                    abs(self.start_point.x() - self.current_point.x()),
                    abs(self.start_point.y() - self.current_point.y())
                )
                painter.drawRect(current_rect)
            
            painter.end()
    
    def clear_rectangles(self):
        self.rectangles = []
        self.image_label.update()
    
    def cut_image(self):
        if not self.image_path or not self.rectangles:
            QMessageBox.warning(self, "Предупреждение", "Загрузите изображение и выделите области для разрезки")
            return
        
        try:
            # Открываем исходное изображение с полным качеством
            pil_image = Image.open(self.image_path)
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            width, height = pil_image.size
            
            # Получаем директорию и имя файла для сохранения результатов
            base_dir = os.path.dirname(self.image_path)
            base_name = os.path.splitext(os.path.basename(self.image_path))[0]
            
            # Получаем масштаб для преобразования координат
            scale_x = width / self.display_pixmap.width()
            scale_y = height / self.display_pixmap.height()
            
            # Обрезаем по каждому прямоугольнику
            for i, rect in enumerate(self.rectangles, 1):
                # Получаем координаты прямоугольника
                qrect = rect.get_qrect()
                left = int(qrect.x() * scale_x)
                top = int(qrect.y() * scale_y)
                right = int((qrect.x() + qrect.width()) * scale_x)
                bottom = int((qrect.y() + qrect.height()) * scale_y)
                
                # Обеспечиваем, чтобы координаты были в пределах изображения
                left = max(0, min(left, width - 1))
                top = max(0, min(top, height - 1))
                right = max(0, min(right, width))
                bottom = max(0, min(bottom, height))
                
                # Обрезаем изображение
                cropped = pil_image.crop((left, top, right, bottom))
                
                # Формируем имя выходного файла
                output_path = os.path.join(base_dir, f"{base_name}_cutted_{i}.tiff")
                
                # Сохраняем с оригинальным качеством
                cropped.save(output_path, format="TIFF", compression="tiff_lzw")
            
            QMessageBox.information(self, "Готово", f"Изображение разрезано на {len(self.rectangles)} частей и сохранено в:\n{base_dir}")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось разрезать изображение: {str(e)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ImageCutterApp()
    window.show()
    sys.exit(app.exec_()) 