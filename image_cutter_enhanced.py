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

class Line:
    def __init__(self, start, end):
        self.start = start
        self.end = end
        
    def get_qline(self):
        return QLine(self.start, self.end)
    
    def to_cv_coords(self, scale_factor):
        """Преобразует координаты в формат OpenCV с учетом масштаба"""
        return (
            (int(self.start.x() / scale_factor), int(self.start.y() / scale_factor)),
            (int(self.end.x() / scale_factor), int(self.end.y() / scale_factor))
        )
    
    def to_shapely_line(self):
        """Преобразует линию в объект Shapely LineString для вычисления пересечений"""
        return LineString([(self.start.x(), self.start.y()), (self.end.x(), self.end.y())])

class ImageCutterAppEnhanced(QMainWindow):
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
        
        # Кнопка для очистки линий
        self.btn_clear = QPushButton("Очистить линии")
        self.btn_clear.clicked.connect(self.clear_lines)
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
                
                # Очищаем линии
                self.lines = []
                
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
            self.status_bar.showMessage(f"Начата линия в точке ({self.start_point.x()}, {self.start_point.y()})")
    
    def mouse_move_event(self, event):
        if self.drawing:
            self.current_point = event.pos()
            self.image_label.update()
            self.status_bar.showMessage(f"Рисование линии: ({self.start_point.x()}, {self.start_point.y()}) -> ({self.current_point.x()}, {self.current_point.y()})")
    
    def mouse_release_event(self, event):
        if self.drawing and event.button() == Qt.LeftButton:
            self.drawing = False
            end_point = event.pos()
            
            # Добавляем линию только если расстояние между точками достаточно большое
            if (self.start_point - end_point).manhattanLength() > 10:
                self.lines.append(Line(self.start_point, end_point))
                self.status_bar.showMessage(f"Добавлена линия: ({self.start_point.x()}, {self.start_point.y()}) -> ({end_point.x()}, {end_point.y()}). Всего линий: {len(self.lines)}")
            else:
                self.status_bar.showMessage("Линия слишком короткая и не была добавлена")
            
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
        self.status_bar.showMessage("Все линии очищены")
    
    def _find_line_intersection(self, line1, line2):
        """Находит точку пересечения двух линий, если она существует"""
        shapely_line1 = line1.to_shapely_line()
        shapely_line2 = line2.to_shapely_line()
        
        if shapely_line1.intersects(shapely_line2):
            intersection = shapely_line1.intersection(shapely_line2)
            if isinstance(intersection, Point):
                return (int(intersection.x), int(intersection.y))
        
        return None
    
    def _get_edge_intersection(self, line, width, height):
        """Находит точки пересечения линии с краями изображения"""
        # Преобразуем линию в параметрическое представление y = mx + b
        start, end = line.start, line.end
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        
        intersections = []
        
        # Если линия вертикальная
        if abs(dx) < 1:
            # Пересечения с верхней и нижней границами
            intersections.append((start.x(), 0))
            intersections.append((start.x(), height - 1))
            return intersections
        
        # Если линия горизонтальная
        if abs(dy) < 1:
            # Пересечения с левой и правой границами
            intersections.append((0, start.y()))
            intersections.append((width - 1, start.y()))
            return intersections
        
        # Для наклонных линий вычисляем параметры y = mx + b
        m = dy / dx
        b = start.y() - m * start.x()
        
        # Левая граница (x = 0)
        left_y = b
        if 0 <= left_y < height:
            intersections.append((0, int(left_y)))
        
        # Правая граница (x = width-1)
        right_y = m * (width-1) + b
        if 0 <= right_y < height:
            intersections.append((width-1, int(right_y)))
        
        # Верхняя граница (y = 0)
        top_x = -b / m if m != 0 else 0
        if 0 <= top_x < width:
            intersections.append((int(top_x), 0))
        
        # Нижняя граница (y = height-1)
        bottom_x = (height-1 - b) / m if m != 0 else 0
        if 0 <= bottom_x < width:
            intersections.append((int(bottom_x), height-1))
        
        return intersections
    
    def _extend_lines_to_edges_and_intersections(self, width, height):
        """
        Продлевает линии до пересечения с другими линиями или краями изображения
        и возвращает список всех сегментов линий для рисования
        """
        if not self.lines:
            return []
        
        # Создаем копию линий для работы
        original_lines = self.lines.copy()
        # Список сегментов линий для рисования
        line_segments = []
        
        # Сначала находим все пересечения
        intersections = []
        for i, line1 in enumerate(original_lines):
            # Добавляем начальную и конечную точки линии
            intersections.append((line1.start.x(), line1.start.y()))
            intersections.append((line1.end.x(), line1.end.y()))
            
            # Находим пересечения с другими линиями
            for j, line2 in enumerate(original_lines):
                if i != j:  # Не проверяем линию с самой собой
                    intersection = self._find_line_intersection(line1, line2)
                    if intersection:
                        intersections.append(intersection)
            
            # Находим пересечения с краями изображения
            edge_intersections = self._get_edge_intersection(line1, width, height)
            intersections.extend(edge_intersections)
        
        # Удаляем дубликаты и сортируем точки
        unique_intersections = list(set(intersections))
        
        # Проходим по каждой линии и создаем сегменты
        for line in original_lines:
            # Преобразуем линию в параметрическое представление
            shapely_line = line.to_shapely_line()
            
            # Находим все точки, лежащие на линии
            points_on_line = []
            for point in unique_intersections:
                shapely_point = Point(point)
                if shapely_line.distance(shapely_point) < 1:  # Небольшой допуск для численной стабильности
                    points_on_line.append(point)
            
            # Сортируем точки вдоль линии
            if len(points_on_line) >= 2:
                # Для сортировки используем расстояние от начальной точки
                start_x, start_y = line.start.x(), line.start.y()
                points_on_line.sort(key=lambda p: ((p[0] - start_x) ** 2 + (p[1] - start_y) ** 2) ** 0.5)
                
                # Создаем сегменты из отсортированных точек
                for i in range(len(points_on_line) - 1):
                    start_point = points_on_line[i]
                    end_point = points_on_line[i + 1]
                    # Добавляем сегмент только если точки разные
                    if start_point != end_point:
                        line_segments.append((start_point, end_point))
        
        return line_segments
    
    def _find_regions(self, image_size):
        """Находит все замкнутые области, образованные линиями"""
        if not self.lines:
            return []
        
        width, height = image_size
        
        # Создаём пустое изображение для рисования линий
        mask = np.ones((height, width), dtype=np.uint8) * 255
        
        # Получаем расширенные линии с учетом пересечений
        extended_lines = self._extend_lines_to_edges_and_intersections(width, height)
        
        # Рисуем все сегменты линий на маске
        for (start_x, start_y), (end_x, end_y) in extended_lines:
            cv2.line(mask, (int(start_x), int(start_y)), (int(end_x), int(end_y)), 0, 1)
        
        # Для отладки: сохраняем маску, чтобы визуально проверить линии
        # cv2.imwrite("debug_mask.png", mask)
        
        # Находим связные компоненты (области)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=4)
        
        # Собираем информацию о регионах
        regions = []
        for i in range(1, num_labels):  # Пропускаем фон (метка 0)
            x, y, w, h, area = stats[i]
            
            # Для проверки - если область слишком маленькая, пропускаем
            if area < 100:  # Минимальная площадь области
                continue
            
            # Создаем маску для этой области
            region_mask = (labels == i).astype(np.uint8) * 255
            
            # Находим контур области
            contours, _ = cv2.findContours(region_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # Берем самый большой контур
                contour = max(contours, key=cv2.contourArea)
                
                # Получаем ограничивающий прямоугольник
                x, y, w, h = cv2.boundingRect(contour)
                
                # Добавляем регион
                regions.append((x, y, x + w, y + h, contour))
        
        return regions
    
    def cut_image(self):
        if not self.image_path:
            QMessageBox.warning(self, "Предупреждение", "Сначала загрузите изображение")
            return
        
        if not self.lines:
            QMessageBox.warning(self, "Предупреждение", "Нарисуйте линии разреза перед разрезкой")
            return
        
        try:
            self.status_bar.showMessage("Выполняется разрезка изображения...")
            
            # Открываем исходное изображение с полным качеством
            pil_image = Image.open(self.image_path)
            original_mode = pil_image.mode
            
            if original_mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # Конвертируем PIL.Image в формат numpy для OpenCV
            img_np = np.array(pil_image)
            
            # Находим области на масштабированном изображении
            preview_width = self.display_pixmap.width()
            preview_height = self.display_pixmap.height()
            regions = self._find_regions((preview_width, preview_height))
            
            if not regions:
                QMessageBox.warning(self, "Предупреждение", "Не удалось обнаружить области для разрезки. Попробуйте добавить больше линий, чтобы сформировать замкнутые области.")
                self.status_bar.showMessage("Области для разрезки не найдены")
                return
            
            # Получаем директорию и имя файла для сохранения результатов
            output_dir = QFileDialog.getExistingDirectory(self, "Выберите папку для сохранения результатов")
            if not output_dir:
                self.status_bar.showMessage("Операция отменена")
                return
            
            base_name = os.path.splitext(os.path.basename(self.image_path))[0]
            
            # Масштабируем координаты областей обратно к оригинальному размеру
            orig_width, orig_height = self.original_size
            scale_x = orig_width / preview_width
            scale_y = orig_height / preview_height
            
            # Обрезаем и сохраняем каждую область
            saved_count = 0
            for i, (x1, y1, x2, y2, contour) in enumerate(regions, 1):
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
                
                self.status_bar.showMessage(f"Сохранена область {i} из {len(regions)}: {output_filename}")
            
            if saved_count > 0:
                QMessageBox.information(self, "Готово", f"Изображение успешно разрезано на {saved_count} частей и сохранено в:\n{output_dir}")
                self.status_bar.showMessage(f"Готово: сохранено {saved_count} областей")
            else:
                QMessageBox.warning(self, "Предупреждение", "Не удалось сохранить ни одной области. Проверьте линии разреза.")
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