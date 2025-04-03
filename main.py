import sys
import os
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QPushButton, 
                            QVBoxLayout, QHBoxLayout, QWidget, QFileDialog, 
                            QMessageBox, QScrollArea)
from PyQt5.QtGui import QPixmap, QPainter, QPen, QImage
from PyQt5.QtCore import Qt, QPoint, QRect, QLine
from PIL import Image

class Line:
    def __init__(self, start, end):
        self.start = start
        self.end = end
        
    def get_qline(self):
        return QLine(self.start, self.end)

class ImageCutterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        
        # Переменные для работы с изображением
        self.image_path = None
        self.original_pixmap = None
        self.display_pixmap = None
        self.lines = []
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
        
        # Кнопка для очистки линий
        self.btn_clear = QPushButton("Очистить линии")
        self.btn_clear.clicked.connect(self.clear_lines)
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
                
                # Очищаем линии
                self.lines = []
                
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
            # Добавляем линию только если расстояние между точками достаточно большое
            if (self.start_point - event.pos()).manhattanLength() > 10:
                self.lines.append(Line(self.start_point, event.pos()))
            self.image_label.update()
    
    def paint_event(self, event):
        if self.display_pixmap:
            painter = QPainter(self.image_label)
            
            # Отрисовка изображения
            painter.drawPixmap(0, 0, self.display_pixmap)
            
            # Настройка пера для линий
            pen = QPen(Qt.red, 2, Qt.SolidLine)
            painter.setPen(pen)
            
            # Отрисовка существующих линий
            for line in self.lines:
                painter.drawLine(line.get_qline())
            
            # Отрисовка линии, которая сейчас рисуется
            if self.drawing:
                painter.drawLine(self.start_point, self.current_point)
            
            painter.end()
    
    def clear_lines(self):
        self.lines = []
        self.image_label.update()
    
    def _find_regions(self):
        """Находит все замкнутые области, образованные линиями"""
        if not self.lines or not self.display_pixmap:
            return []
        
        # Создаем маску того же размера, что и изображение
        width = self.display_pixmap.width()
        height = self.display_pixmap.height()
        
        # Рисуем все линии на временном изображении
        temp_image = QImage(width, height, QImage.Format_ARGB32)
        temp_image.fill(Qt.white)
        
        painter = QPainter(temp_image)
        painter.setPen(QPen(Qt.black, 1, Qt.SolidLine))
        
        # Рисуем линии и продлеваем их до краев изображения
        for line in self.lines:
            # Рисуем оригинальную линию
            painter.drawLine(line.get_qline())
            
            # Продлеваем линию до краев изображения
            start, end = line.start, line.end
            
            # Вычисляем направление линии
            dx = end.x() - start.x()
            dy = end.y() - start.y()
            
            # Если линия вертикальная
            if dx == 0:
                painter.drawLine(start.x(), 0, start.x(), height)
            # Если линия горизонтальная
            elif dy == 0:
                painter.drawLine(0, start.y(), width, start.y())
            # Для наклонных линий
            else:
                # Вычисляем параметры прямой y = mx + b
                m = dy / dx
                b = start.y() - m * start.x()
                
                # Находим точки пересечения с границами изображения
                # Левая граница (x = 0)
                left_y = int(b)
                if 0 <= left_y < height:
                    left_point = QPoint(0, left_y)
                else:
                    left_point = None
                
                # Правая граница (x = width-1)
                right_y = int(m * (width-1) + b)
                if 0 <= right_y < height:
                    right_point = QPoint(width-1, right_y)
                else:
                    right_point = None
                
                # Верхняя граница (y = 0)
                top_x = int(-b / m) if m != 0 else 0
                if 0 <= top_x < width:
                    top_point = QPoint(top_x, 0)
                else:
                    top_point = None
                
                # Нижняя граница (y = height-1)
                bottom_x = int((height-1 - b) / m) if m != 0 else 0
                if 0 <= bottom_x < width:
                    bottom_point = QPoint(bottom_x, height-1)
                else:
                    bottom_point = None
                
                # Рисуем продолженные линии
                points = [p for p in [left_point, right_point, top_point, bottom_point] if p is not None]
                if len(points) >= 2:
                    painter.drawLine(points[0], points[1])
        
        painter.end()
        
        # Теперь у нас есть изображение с линиями, можно найти и заполнить области
        # Этот код будет находить все области и возвращать их границы
        
        # Для простоты сейчас просто вернем все изображение как одну область
        # В реальном приложении здесь должен быть более сложный алгоритм поиска областей
        return [QRect(0, 0, width, height)]
    
    def cut_image(self):
        if not self.image_path or not self.lines:
            QMessageBox.warning(self, "Предупреждение", "Загрузите изображение и нарисуйте линии разреза")
            return
        
        # Для простоты реализации, сейчас просто разрежем изображение по квадрантам
        # В полной реализации здесь должен быть вызов функции _find_regions()
        
        try:
            # Открываем исходное изображение с полным качеством
            pil_image = Image.open(self.image_path)
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            width, height = pil_image.size
            
            # Получаем директорию и имя файла для сохранения результатов
            base_dir = os.path.dirname(self.image_path)
            base_name = os.path.splitext(os.path.basename(self.image_path))[0]
            
            # Для демонстрации разобьем изображение на 4 части
            # Это упрощенная версия, которая будет заменена на алгоритм поиска областей
            regions = [
                (0, 0, width // 2, height // 2),
                (width // 2, 0, width, height // 2),
                (0, height // 2, width // 2, height),
                (width // 2, height // 2, width, height)
            ]
            
            for i, (left, top, right, bottom) in enumerate(regions, 1):
                # Обрезаем изображение
                cropped = pil_image.crop((left, top, right, bottom))
                
                # Формируем имя выходного файла
                output_path = os.path.join(base_dir, f"{base_name}_cutted_{i}.tiff")
                
                # Сохраняем с оригинальным качеством
                cropped.save(output_path, format="TIFF", compression="tiff_lzw")
            
            QMessageBox.information(self, "Готово", f"Изображение разрезано на 4 части и сохранено в:\n{base_dir}")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось разрезать изображение: {str(e)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ImageCutterApp()
    window.show()
    sys.exit(app.exec_()) 