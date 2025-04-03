import sys
import os
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QPushButton, 
                            QVBoxLayout, QHBoxLayout, QWidget, QFileDialog, 
                            QMessageBox, QScrollArea, QStatusBar)
from PyQt5.QtGui import QPixmap, QPainter, QPen, QImage, QColor
from PyQt5.QtCore import Qt, QPoint, QRect, QLine
from PIL import Image, ImageDraw
import cv2
import uuid
from shapely.geometry import LineString, Point

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
    
    def to_cv_coords(self, scale_factor):
        """Преобразует координаты в формат OpenCV с учетом масштаба"""
        x1 = min(self.start.x(), self.end.x()) / scale_factor
        y1 = min(self.start.y(), self.end.y()) / scale_factor
        x2 = max(self.start.x(), self.end.x()) / scale_factor
        y2 = max(self.start.y(), self.end.y()) / scale_factor
        return (int(x1), int(y1), int(x2), int(y2))

class ImageCutterAppEnhanced(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        
        # Переменные для работы с изображением
        self.image_path = None
        self.original_pixmap = None
        self.display_pixmap = None
        self.rectangles = []  # Список прямоугольников вместо линий
        self.drawing = False
        self.start_point = None
        self.current_point = None
        self.original_size = None  # Размер оригинального изображения
        self.scale_factor = 1.0    # Коэффициент масштабирования для предпросмотра
        
    def init_ui(self):
        self.setWindowTitle('Разрезка сканированных изображений')
        self.setGeometry(100, 100, 1400, 900)
        
        # Создание главного виджета и компоновки
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # Виджет для прокрутки изображения
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        
        # Создание виджета для отображения изображения
        self.image_label = QLabel("Загрузите изображение (*.tif или *.tiff)")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(1000, 700)
        self.image_label.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
        
        # Переопределяем обработчики событий мыши
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
        self.btn_open.setMinimumWidth(150)
        button_layout.addWidget(self.btn_open)
        
        # Кнопка для очистки прямоугольников
        self.btn_clear = QPushButton("Очистить выделения")
        self.btn_clear.clicked.connect(self.clear_rectangles)
        self.btn_clear.setMinimumWidth(150)
        self.btn_clear.setEnabled(False)
        button_layout.addWidget(self.btn_clear)
        
        # Кнопка для разрезки изображения
        self.btn_cut = QPushButton("Разрезать")
        self.btn_cut.clicked.connect(self.cut_image)
        self.btn_cut.setMinimumWidth(150)
        self.btn_cut.setEnabled(False)
        button_layout.addWidget(self.btn_cut)
        
        main_layout.addLayout(button_layout)
        
        # Добавление строки состояния
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готово")
        
        self.setCentralWidget(main_widget)
        
    def open_image(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self, "Выберите изображение", "", "Изображения (*.tif *.tiff)"
        )
        
        if file_path:
            try:
                self.status_bar.showMessage(f"Загрузка изображения: {file_path}")
                self.image_path = file_path
                
                # Загружаем оригинальное изображение через PIL для поддержки TIFF
                pil_image = Image.open(file_path)
                # Сохраняем оригинальный размер
                self.original_size = pil_image.size
                
                # Конвертируем в RGB, если нужно
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')
                
                # Преобразуем для отображения с уменьшенным размером для предпросмотра
                # Максимальный размер для отображения
                max_width = 1200
                max_height = 800
                width, height = pil_image.size
                
                self.scale_factor = min(max_width / width, max_height / height)
                new_width = int(width * self.scale_factor)
                new_height = int(height * self.scale_factor)
                
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
                
                # Очищаем прямоугольники
                self.rectangles = []
                
                # Устанавливаем размер виджета и обновляем интерфейс
                self.btn_clear.setEnabled(True)
                self.btn_cut.setEnabled(True)
                
                self.status_bar.showMessage(f"Изображение загружено: {width}x{height} пикселей")
                
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось открыть изображение: {str(e)}")
                self.status_bar.showMessage("Ошибка при загрузке изображения")
    
    def mouse_press_event(self, event):
        if self.display_pixmap and event.button() == Qt.LeftButton:
            self.drawing = True
            self.start_point = event.pos()
            self.current_point = event.pos()
            self.status_bar.showMessage(f"Начато выделение в точке ({self.start_point.x()}, {self.start_point.y()})")
    
    def mouse_move_event(self, event):
        if self.drawing:
            self.current_point = event.pos()
            self.image_label.update()
            self.status_bar.showMessage(f"Рисование прямоугольника: ({self.start_point.x()}, {self.start_point.y()}) -> ({self.current_point.x()}, {self.current_point.y()})")
    
    def mouse_release_event(self, event):
        if self.drawing and event.button() == Qt.LeftButton:
            self.drawing = False
            end_point = event.pos()
            
            # Добавляем прямоугольник только если его размер достаточно большой
            if (self.start_point - end_point).manhattanLength() > 10:
                self.rectangles.append(Rectangle(self.start_point, end_point))
                rect = Rectangle(self.start_point, end_point).get_qrect()
                self.status_bar.showMessage(f"Добавлен прямоугольник: ({rect.x()}, {rect.y()}, {rect.width()}x{rect.height()}). Всего областей: {len(self.rectangles)}")
            else:
                self.status_bar.showMessage("Прямоугольник слишком маленький и не был добавлен")
            
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
        """Очищает все прямоугольники"""
        self.rectangles = []
        self.image_label.update()
        self.status_bar.showMessage("Все выделения очищены")
    
    def cut_image(self):
        if not self.image_path:
            QMessageBox.warning(self, "Предупреждение", "Сначала загрузите изображение")
            return
        
        if not self.rectangles:
            QMessageBox.warning(self, "Предупреждение", "Выделите области перед разрезкой")
            return
        
        try:
            self.status_bar.showMessage("Выполняется разрезка изображения...")
            
            # Открываем исходное изображение с полным качеством
            pil_image = Image.open(self.image_path)
            original_mode = pil_image.mode
            
            if original_mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # Получаем директорию и имя файла для сохранения результатов
            output_dir = QFileDialog.getExistingDirectory(self, "Выберите папку для сохранения результатов")
            if not output_dir:
                self.status_bar.showMessage("Операция отменена")
                return
            
            base_name = os.path.splitext(os.path.basename(self.image_path))[0]
            
            # Масштабируем координаты областей обратно к оригинальному размеру
            orig_width, orig_height = self.original_size
            preview_width = self.display_pixmap.width()
            preview_height = self.display_pixmap.height()
            scale_x = orig_width / preview_width
            scale_y = orig_height / preview_height
            
            # Обрезаем и сохраняем каждую область
            saved_count = 0
            for i, rect in enumerate(self.rectangles, 1):
                # Получаем координаты прямоугольника и масштабируем их к оригинальному размеру
                x1, y1, x2, y2 = rect.to_cv_coords(1.0)  # Получаем координаты без масштабирования
                
                # Масштабируем координаты к оригинальному размеру
                orig_x1 = int(x1 * scale_x)
                orig_y1 = int(y1 * scale_y)
                orig_x2 = int(x2 * scale_x)
                orig_y2 = int(y2 * scale_y)
                
                # Обеспечиваем, чтобы координаты были в пределах изображения
                orig_x1 = max(0, min(orig_x1, orig_width - 1))
                orig_y1 = max(0, min(orig_y1, orig_height - 1))
                orig_x2 = max(0, min(orig_x2, orig_width))
                orig_y2 = max(0, min(orig_y2, orig_height))
                
                # Проверяем размер области
                if orig_x2 - orig_x1 < 10 or orig_y2 - orig_y1 < 10:
                    continue  # Пропускаем слишком маленькие области
                
                # Обрезаем изображение
                cropped = pil_image.crop((orig_x1, orig_y1, orig_x2, orig_y2))
                
                # Формируем имя выходного файла
                output_filename = f"{base_name}_cutted_{i}.tiff"
                output_path = os.path.join(output_dir, output_filename)
                
                # Возвращаем к оригинальному формату, если необходимо
                if original_mode != 'RGB':
                    cropped = cropped.convert(original_mode)
                
                # Сохраняем с оригинальным качеством
                cropped.save(output_path, format="TIFF", compression="tiff_lzw")
                saved_count += 1
                
                self.status_bar.showMessage(f"Сохранена область {i} из {len(self.rectangles)}: {output_filename}")
            
            if saved_count > 0:
                QMessageBox.information(self, "Готово", f"Изображение успешно разрезано на {saved_count} частей и сохранено в:\n{output_dir}")
                self.status_bar.showMessage(f"Готово: сохранено {saved_count} областей")
            else:
                QMessageBox.warning(self, "Предупреждение", "Не удалось сохранить ни одной области. Проверьте выделения.")
                self.status_bar.showMessage("Не удалось сохранить ни одной области")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось разрезать изображение: {str(e)}")
            self.status_bar.showMessage(f"Ошибка: {str(e)}")
            print(f"Ошибка: {str(e)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Устанавливаем стиль приложения
    window = ImageCutterAppEnhanced()
    window.show()
    sys.exit(app.exec_()) 