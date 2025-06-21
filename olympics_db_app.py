import psycopg2
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv

class DBApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Olympics DB Interface")
        self.conn = None
        self.last_result = None
        self.current_table = None
        self.all_columns = []
        self.filter_vars = {}
        self.sort_column = None
        self.sort_reverse = False

        # Фрейм подключения
        frame_conn = ttk.LabelFrame(root, text="Подключение к БД")
        frame_conn.pack(fill='x', padx=10, pady=5)

        self.e_host = ttk.Entry(frame_conn, width=12)
        self.e_host.insert(0, 'localhost')
        self.e_port = ttk.Entry(frame_conn, width=6)
        self.e_port.insert(0, '5432')
        self.e_db = ttk.Entry(frame_conn, width=12)
        self.e_db.insert(0, 'olympics_medals')
        self.e_user = ttk.Entry(frame_conn, width=10)
        self.e_user.insert(0, 'postgres')
        self.e_pass = ttk.Entry(frame_conn, width=10, show='*')
        self.e_pass.insert(0, '123')

        for widget, lbl in zip([self.e_host, self.e_port, self.e_db, self.e_user, self.e_pass],
                               ['host', 'port', 'db', 'user', 'pass']):
            ttk.Label(frame_conn, text=lbl).pack(side='left', padx=(2,0))
            widget.pack(side='left', padx=(0,5))
        ttk.Button(frame_conn, text="Подключиться", command=self.connect_db).pack(side='left')

        # Фрейм выбора таблицы
        self.frame_table = ttk.LabelFrame(root, text="Таблицы в базе")
        self.frame_table.pack(fill='x', padx=10, pady=5)
        ttk.Label(self.frame_table, text="Таблица:").pack(side='left')
        self.cb_tables = ttk.Combobox(self.frame_table, state='readonly', width=25)
        self.cb_tables.pack(side='left', padx=5)
        ttk.Button(self.frame_table, text="Показать таблицу", command=self.show_selected_table).pack(side='left')

        # Фрейм фильтров
        self.frame_filters = ttk.LabelFrame(root, text="Фильтрация и сортировка")
        self.frame_filters.pack(fill='x', padx=10, pady=5)

        # Здесь появятся фильтры
        self.filter_frame_inner = ttk.Frame(self.frame_filters)
        self.filter_frame_inner.pack(fill='x')

        ttk.Button(self.frame_filters, text="Применить фильтр/сортировку", command=self.apply_filter).pack(side='left', padx=5)
        ttk.Button(self.frame_filters, text="Сбросить фильтры", command=self.reset_filter).pack(side='left', padx=5)

        # Фрейм результатов
        frame_res = ttk.LabelFrame(root, text="Результаты")
        frame_res.pack(fill='both', expand=True, padx=10, pady=5)

        self.tree = ttk.Treeview(frame_res, show='headings')
        self.tree.pack(fill='both', expand=True)
        self.scroll_y = ttk.Scrollbar(frame_res, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=self.scroll_y.set)
        self.scroll_y.pack(side='right', fill='y')

        # Кнопка экспорта
        ttk.Button(root, text="Экспортировать результат в CSV", command=self.export_csv).pack(pady=3)

    def connect_db(self):
        try:
            self.conn = psycopg2.connect(
                host=self.e_host.get(),
                port=self.e_port.get(),
                dbname=self.e_db.get(),
                user=self.e_user.get(),
                password=self.e_pass.get()
            )
            messagebox.showinfo("Успех", "Соединение с БД успешно установлено!")
            self.load_tables()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка подключения к БД:\n{e}")

    def load_tables(self):
        # Загрузка списка таблиц после подключения
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema='public' AND table_type='BASE TABLE'
                    ORDER BY table_name
                """)
                tables = [row[0] for row in cur.fetchall()]
                self.cb_tables['values'] = tables
                if tables:
                    self.cb_tables.current(0)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка загрузки списка таблиц:\n{e}")

    def show_selected_table(self):
        tbl = self.cb_tables.get()
        if not tbl:
            return
        self.current_table = tbl
        self.filter_vars = {}
        self.sort_column = None
        self.sort_reverse = False
        self.show_query(self.build_select_query())
        self.build_filter_widgets()

    def build_select_query(self):
        query = f"SELECT * FROM {self.current_table}"
        filters = []
        for col, var in self.filter_vars.items():
            val = var.get().strip()
            if val:
                # Если значение число, фильтруем по точному совпадению, иначе LIKE
                if val.isdigit():
                    filters.append(f"{col} = {val}")
                else:
                    filters.append(f"{col} ILIKE '%{val}%'")
        if filters:
            query += " WHERE " + " AND ".join(filters)
        if self.sort_column:
            query += f" ORDER BY {self.sort_column}"
            if self.sort_reverse:
                query += " DESC"
        query += " LIMIT 100"
        return query

    def build_filter_widgets(self):
        # Очистить предыдущее
        for widget in self.filter_frame_inner.winfo_children():
            widget.destroy()
        # Получить названия столбцов
        cols = self.all_columns or []
        self.filter_vars = {}
        for idx, col in enumerate(cols):
            ttk.Label(self.filter_frame_inner, text=col).grid(row=0, column=idx)
            var = tk.StringVar()
            entry = ttk.Entry(self.filter_frame_inner, textvariable=var, width=12)
            entry.grid(row=1, column=idx)
            self.filter_vars[col] = var
            # Добавим кнопки сортировки
            btn_asc = ttk.Button(self.filter_frame_inner, text="↑", width=2, command=lambda c=col: self.sort_by_column(c, False))
            btn_asc.grid(row=2, column=idx)
            btn_desc = ttk.Button(self.filter_frame_inner, text="↓", width=2, command=lambda c=col: self.sort_by_column(c, True))
            btn_desc.grid(row=3, column=idx)

    def apply_filter(self):
        if not self.current_table:
            return
        self.show_query(self.build_select_query())

    def reset_filter(self):
        if not self.current_table:
            return
        for var in self.filter_vars.values():
            var.set("")
        self.sort_column = None
        self.sort_reverse = False
        self.show_query(self.build_select_query())

    def sort_by_column(self, col, reverse):
        self.sort_column = col
        self.sort_reverse = reverse
        self.show_query(self.build_select_query())

    def show_query(self, query):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.last_result = None
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                cols = [desc[0] for desc in cur.description]
                self.all_columns = cols
                self.tree["columns"] = cols
                for c in cols:
                    self.tree.heading(c, text=c)
                    self.tree.column(c, anchor="center", width=120)
                rows = cur.fetchall()
                for row in rows:
                    self.tree.insert("", "end", values=row)
                self.last_result = (cols, rows)
        except Exception as e:
            messagebox.showerror("Ошибка выполнения", str(e))

    def export_csv(self):
        if not self.last_result:
            messagebox.showinfo("Нет данных", "Нет данных для экспорта!")
            return
        cols, rows = self.last_result
        file = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not file:
            return
        try:
            with open(file, "w", newline='', encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(cols)
                writer.writerows(rows)
            messagebox.showinfo("Экспорт", f"Данные успешно экспортированы в файл:\n{file}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при экспорте в CSV:\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = DBApp(root)
    root.geometry("1200x700")
    root.mainloop()
