"""
CanteenBookingSystem.py
A single-file desktop application for managing school canteen lunch bookings.

Tech stack:
- Tkinter for the GUI
- SQLite3 for local persistent storage

Run with: python CanteenBookingSystem.py
Default manager login created on first run: username="admin", password="admin123"
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import hashlib
import csv
from datetime import datetime, date

DB_NAME = "canteen.db"


# ----------------------------------------------------------------------------
# DATABASE LAYER
# ----------------------------------------------------------------------------
class Database:
    def __init__(self, db_name=DB_NAME):
        self.conn = sqlite3.connect(db_name)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.create_tables()
        self.seed_admin()

    def create_tables(self):
        c = self.conn.cursor()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            year_group TEXT
        );

        CREATE TABLE IF NOT EXISTS staff (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('manager','staff')),
            active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS meals (
            meal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            meal_date TEXT NOT NULL,
            name TEXT NOT NULL,
            selling_price REAL NOT NULL,
            prep_cost REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            order_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','cancelled')),
            FOREIGN KEY(student_id) REFERENCES students(student_id),
            UNIQUE(student_id, order_date)
        );

        CREATE TABLE IF NOT EXISTS order_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            meal_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            FOREIGN KEY(order_id) REFERENCES orders(order_id),
            FOREIGN KEY(meal_id) REFERENCES meals(meal_id)
        );
        """)
        self.conn.commit()

    def seed_admin(self):
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) FROM staff")
        if c.fetchone()[0] == 0:
            c.execute(
                "INSERT INTO staff (username, password_hash, role, active) VALUES (?,?,?,1)",
                ("admin", hash_password("admin123"), "manager"),
            )
            self.conn.commit()


def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


# ----------------------------------------------------------------------------
# MAIN APPLICATION
# ----------------------------------------------------------------------------
class CanteenApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Canteen Booking System")
        self.geometry("950x650")
        self.db = Database()
        self.current_user = None  # (username, role)

        self.container = tk.Frame(self)
        self.container.pack(fill="both", expand=True)

        self.show_login()

    # ---------------- Navigation helpers ----------------
    def clear_container(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    def show_login(self):
        self.current_user = None
        self.clear_container()
        LoginFrame(self.container, self)

    def show_main(self):
        self.clear_container()
        MainFrame(self.container, self)


# ----------------------------------------------------------------------------
# LOGIN SCREEN
# ----------------------------------------------------------------------------
class LoginFrame(tk.Frame):
    def __init__(self, parent, app: CanteenApp):
        super().__init__(parent)
        self.app = app
        self.pack(fill="both", expand=True)

        wrapper = tk.Frame(self)
        wrapper.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(wrapper, text="Canteen Booking System", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(0, 20)
        )

        tk.Label(wrapper, text="Username:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.username_entry = tk.Entry(wrapper, width=25)
        self.username_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(wrapper, text="Password:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.password_entry = tk.Entry(wrapper, width=25, show="*")
        self.password_entry.grid(row=2, column=1, padx=5, pady=5)

        tk.Button(wrapper, text="Login", width=15, command=self.attempt_login).grid(
            row=3, column=0, columnspan=2, pady=15
        )

        tk.Label(
            wrapper,
            text="Default manager login: admin / admin123",
            fg="gray",
        ).grid(row=4, column=0, columnspan=2)

        self.password_entry.bind("<Return>", lambda e: self.attempt_login())

    def attempt_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        if not username or not password:
            messagebox.showerror("Error", "Please enter both username and password.")
            return

        c = self.app.db.conn.cursor()
        c.execute("SELECT password_hash, role, active FROM staff WHERE username=?", (username,))
        row = c.fetchone()

        if row is None:
            messagebox.showerror("Login failed", "Invalid username or password.")
            return

        password_hash, role, active = row
        if active == 0:
            messagebox.showerror("Login failed", "This account has been deactivated.")
            return
        if hash_password(password) != password_hash:
            messagebox.showerror("Login failed", "Invalid username or password.")
            return

        self.app.current_user = (username, role)
        self.app.show_main()


# ----------------------------------------------------------------------------
# MAIN FRAME WITH TABS
# ----------------------------------------------------------------------------
class MainFrame(tk.Frame):
    def __init__(self, parent, app: CanteenApp):
        super().__init__(parent)
        self.app = app
        self.pack(fill="both", expand=True)

        username, role = self.app.current_user

        top = tk.Frame(self)
        top.pack(fill="x", padx=10, pady=5)
        tk.Label(
            top, text=f"Logged in as: {username} ({role})", font=("Segoe UI", 10, "bold")
        ).pack(side="left")
        tk.Button(top, text="Logout", command=self.app.show_login).pack(side="right")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        notebook.add(StudentsTab(notebook, app), text="Students")
        notebook.add(MealsTab(notebook, app), text="Meals")
        notebook.add(OrdersTab(notebook, app), text="Orders")
        notebook.add(PreparationTab(notebook, app), text="Preparation")
        notebook.add(ReportsTab(notebook, app), text="Reports")

        if role == "manager":
            notebook.add(StaffTab(notebook, app), text="Staff Accounts")


# ----------------------------------------------------------------------------
# STUDENTS TAB  (Success criteria 1, 2)
# ----------------------------------------------------------------------------
class StudentsTab(tk.Frame):
    def __init__(self, parent, app: CanteenApp):
        super().__init__(parent)
        self.app = app

        form = tk.LabelFrame(self, text="Add / Edit Student")
        form.pack(fill="x", padx=10, pady=10)

        tk.Label(form, text="Student ID:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.id_entry = tk.Entry(form)
        self.id_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(form, text="First Name:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.first_entry = tk.Entry(form)
        self.first_entry.grid(row=0, column=3, padx=5, pady=5)

        tk.Label(form, text="Last Name:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.last_entry = tk.Entry(form)
        self.last_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(form, text="Year Group:").grid(row=1, column=2, padx=5, pady=5, sticky="e")
        self.year_entry = tk.Entry(form)
        self.year_entry.grid(row=1, column=3, padx=5, pady=5)

        btns = tk.Frame(form)
        btns.grid(row=2, column=0, columnspan=4, pady=10)
        tk.Button(btns, text="Add Student", command=self.add_student).pack(side="left", padx=5)
        tk.Button(btns, text="Update Selected", command=self.update_student).pack(side="left", padx=5)
        tk.Button(btns, text="Clear Form", command=self.clear_form).pack(side="left", padx=5)

        self.tree = ttk.Treeview(
            self, columns=("id", "first", "last", "year"), show="headings", height=15
        )
        for col, text, w in [
            ("id", "Student ID", 120),
            ("first", "First Name", 150),
            ("last", "Last Name", 150),
            ("year", "Year Group", 100),
        ]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.tree.bind("<<TreeviewSelect>>", self.load_selected)

        self.refresh_list()

    def clear_form(self):
        self.id_entry.delete(0, tk.END)
        self.first_entry.delete(0, tk.END)
        self.last_entry.delete(0, tk.END)
        self.year_entry.delete(0, tk.END)
        self.id_entry.config(state="normal")

    def validate_fields(self):
        if not self.id_entry.get().strip():
            messagebox.showerror("Missing field", "Student ID is required.")
            return False
        if not self.first_entry.get().strip():
            messagebox.showerror("Missing field", "First name is required.")
            return False
        if not self.last_entry.get().strip():
            messagebox.showerror("Missing field", "Last name is required.")
            return False
        return True

    def add_student(self):
        if not self.validate_fields():
            return
        sid = self.id_entry.get().strip()
        c = self.app.db.conn.cursor()
        c.execute("SELECT 1 FROM students WHERE student_id=?", (sid,))
        if c.fetchone():
            messagebox.showerror("Duplicate ID", f"Student ID '{sid}' already exists.")
            return
        c.execute(
            "INSERT INTO students (student_id, first_name, last_name, year_group) VALUES (?,?,?,?)",
            (sid, self.first_entry.get().strip(), self.last_entry.get().strip(), self.year_entry.get().strip()),
        )
        self.app.db.conn.commit()
        messagebox.showinfo("Success", "Student added.")
        self.clear_form()
        self.refresh_list()

    def update_student(self):
        if not self.validate_fields():
            return
        sid = self.id_entry.get().strip()
        c = self.app.db.conn.cursor()
        c.execute("SELECT 1 FROM students WHERE student_id=?", (sid,))
        if not c.fetchone():
            messagebox.showerror("Not found", f"No student with ID '{sid}' exists to update.")
            return
        c.execute(
            "UPDATE students SET first_name=?, last_name=?, year_group=? WHERE student_id=?",
            (self.first_entry.get().strip(), self.last_entry.get().strip(), self.year_entry.get().strip(), sid),
        )
        self.app.db.conn.commit()
        messagebox.showinfo("Success", "Student updated.")
        self.clear_form()
        self.refresh_list()

    def load_selected(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        self.clear_form()
        self.id_entry.insert(0, values[0])
        self.id_entry.config(state="normal")
        self.first_entry.insert(0, values[1])
        self.last_entry.insert(0, values[2])
        self.year_entry.insert(0, values[3])

    def refresh_list(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        c = self.app.db.conn.cursor()
        c.execute("SELECT student_id, first_name, last_name, year_group FROM students ORDER BY student_id")
        for row in c.fetchall():
            self.tree.insert("", "end", values=row)


# ----------------------------------------------------------------------------
# MEALS TAB (Success criterion 3)
# ----------------------------------------------------------------------------
class MealsTab(tk.Frame):
    def __init__(self, parent, app: CanteenApp):
        super().__init__(parent)
        self.app = app

        form = tk.LabelFrame(self, text="Add / Edit Meal")
        form.pack(fill="x", padx=10, pady=10)

        tk.Label(form, text="Date (YYYY-MM-DD):").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.date_entry = tk.Entry(form)
        self.date_entry.insert(0, date.today().isoformat())
        self.date_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(form, text="Meal Name:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.name_entry = tk.Entry(form)
        self.name_entry.grid(row=0, column=3, padx=5, pady=5)

        tk.Label(form, text="Selling Price:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.price_entry = tk.Entry(form)
        self.price_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(form, text="Prep Cost:").grid(row=1, column=2, padx=5, pady=5, sticky="e")
        self.cost_entry = tk.Entry(form)
        self.cost_entry.grid(row=1, column=3, padx=5, pady=5)

        self.selected_meal_id = None

        btns = tk.Frame(form)
        btns.grid(row=2, column=0, columnspan=4, pady=10)
        tk.Button(btns, text="Add Meal", command=self.add_meal).pack(side="left", padx=5)
        tk.Button(btns, text="Update Selected", command=self.update_meal).pack(side="left", padx=5)
        tk.Button(btns, text="Clear Form", command=self.clear_form).pack(side="left", padx=5)

        self.tree = ttk.Treeview(
            self, columns=("id", "date", "name", "price", "cost"), show="headings", height=15
        )
        for col, text, w in [
            ("id", "Meal ID", 60),
            ("date", "Date", 100),
            ("name", "Meal Name", 220),
            ("price", "Selling Price", 100),
            ("cost", "Prep Cost", 100),
        ]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.tree.bind("<<TreeviewSelect>>", self.load_selected)

        self.refresh_list()

    def clear_form(self):
        self.selected_meal_id = None
        self.date_entry.delete(0, tk.END)
        self.date_entry.insert(0, date.today().isoformat())
        self.name_entry.delete(0, tk.END)
        self.price_entry.delete(0, tk.END)
        self.cost_entry.delete(0, tk.END)

    def validate_fields(self):
        if not self.date_entry.get().strip() or not self.name_entry.get().strip():
            messagebox.showerror("Missing field", "Date and meal name are required.")
            return False
        try:
            datetime.strptime(self.date_entry.get().strip(), "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Invalid date", "Date must be in YYYY-MM-DD format.")
            return False
        try:
            float(self.price_entry.get())
            float(self.cost_entry.get())
        except ValueError:
            messagebox.showerror("Invalid number", "Selling price and prep cost must be numeric.")
            return False
        return True

    def add_meal(self):
        if not self.validate_fields():
            return
        c = self.app.db.conn.cursor()
        c.execute(
            "INSERT INTO meals (meal_date, name, selling_price, prep_cost) VALUES (?,?,?,?)",
            (
                self.date_entry.get().strip(),
                self.name_entry.get().strip(),
                float(self.price_entry.get()),
                float(self.cost_entry.get()),
            ),
        )
        self.app.db.conn.commit()
        messagebox.showinfo("Success", "Meal added.")
        self.clear_form()
        self.refresh_list()

    def update_meal(self):
        if self.selected_meal_id is None:
            messagebox.showerror("No selection", "Select a meal from the list to update.")
            return
        if not self.validate_fields():
            return
        c = self.app.db.conn.cursor()
        c.execute(
            "UPDATE meals SET meal_date=?, name=?, selling_price=?, prep_cost=? WHERE meal_id=?",
            (
                self.date_entry.get().strip(),
                self.name_entry.get().strip(),
                float(self.price_entry.get()),
                float(self.cost_entry.get()),
                self.selected_meal_id,
            ),
        )
        self.app.db.conn.commit()
        messagebox.showinfo("Success", "Meal updated.")
        self.clear_form()
        self.refresh_list()

    def load_selected(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        self.selected_meal_id = values[0]
        self.date_entry.delete(0, tk.END)
        self.date_entry.insert(0, values[1])
        self.name_entry.delete(0, tk.END)
        self.name_entry.insert(0, values[2])
        self.price_entry.delete(0, tk.END)
        self.price_entry.insert(0, values[3])
        self.cost_entry.delete(0, tk.END)
        self.cost_entry.insert(0, values[4])

    def refresh_list(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        c = self.app.db.conn.cursor()
        c.execute("SELECT meal_id, meal_date, name, selling_price, prep_cost FROM meals ORDER BY meal_date DESC")
        for row in c.fetchall():
            self.tree.insert("", "end", values=row)


# ----------------------------------------------------------------------------
# ORDERS TAB (Success criteria 4, 5, 6, 7)
# ----------------------------------------------------------------------------
class OrdersTab(tk.Frame):
    def __init__(self, parent, app: CanteenApp):
        super().__init__(parent)
        self.app = app
        self.current_order_id = None
        self.order_items = []  # list of (meal_id, meal_name, quantity)

        top = tk.LabelFrame(self, text="Create / Manage Order")
        top.pack(fill="x", padx=10, pady=10)

        tk.Label(top, text="Student ID:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.student_entry = tk.Entry(top, width=15)
        self.student_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(top, text="Order Date (YYYY-MM-DD):").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.date_entry = tk.Entry(top, width=15)
        self.date_entry.insert(0, date.today().isoformat())
        self.date_entry.grid(row=0, column=3, padx=5, pady=5)

        tk.Button(top, text="Load / Start Order", command=self.load_order).grid(row=0, column=4, padx=10)

        tk.Label(top, text="Meal:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.meal_combo = ttk.Combobox(top, width=30, state="readonly")
        self.meal_combo.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky="w")

        tk.Label(top, text="Quantity:").grid(row=1, column=3, padx=5, pady=5, sticky="e")
        self.qty_entry = tk.Entry(top, width=8)
        self.qty_entry.insert(0, "1")
        self.qty_entry.grid(row=1, column=4, padx=5, pady=5, sticky="w")

        tk.Button(top, text="Add Meal to Order", command=self.add_item).grid(row=1, column=5, padx=5)

        mid = tk.Frame(self)
        mid.pack(fill="both", expand=True, padx=10, pady=5)

        self.items_tree = ttk.Treeview(mid, columns=("meal", "qty"), show="headings", height=8)
        self.items_tree.heading("meal", text="Meal")
        self.items_tree.heading("qty", text="Quantity")
        self.items_tree.pack(fill="both", expand=True, side="left")

        btn_col = tk.Frame(mid)
        btn_col.pack(side="left", padx=10, fill="y")
        tk.Button(btn_col, text="Remove Selected Item", command=self.remove_item).pack(pady=5)
        tk.Button(btn_col, text="Save Order", command=self.save_order).pack(pady=5)
        tk.Button(btn_col, text="Cancel Order", command=self.cancel_order).pack(pady=5)

        search = tk.LabelFrame(self, text="Search Orders by Student ID")
        search.pack(fill="x", padx=10, pady=5)
        tk.Label(search, text="Student ID:").pack(side="left", padx=5)
        self.search_entry = tk.Entry(search, width=15)
        self.search_entry.pack(side="left", padx=5)
        tk.Button(search, text="Search", command=self.search_orders).pack(side="left", padx=5)

        self.results_tree = ttk.Treeview(
            self, columns=("order_id", "student", "date", "status"), show="headings", height=8
        )
        for col, text, w in [
            ("order_id", "Order ID", 80),
            ("student", "Student ID", 100),
            ("date", "Date", 100),
            ("status", "Status", 100),
        ]:
            self.results_tree.heading(col, text=text)
            self.results_tree.column(col, width=w)
        self.results_tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.refresh_meal_options()

    def refresh_meal_options(self):
        c = self.app.db.conn.cursor()
        c.execute("SELECT meal_id, name, meal_date FROM meals ORDER BY meal_date DESC")
        self.meal_map = {}
        display = []
        for mid, name, mdate in c.fetchall():
            label = f"{mdate} - {name} (#{mid})"
            self.meal_map[label] = mid
            display.append(label)
        self.meal_combo["values"] = display

    def load_order(self):
        sid = self.student_entry.get().strip()
        odate = self.date_entry.get().strip()
        if not sid or not odate:
            messagebox.showerror("Missing field", "Enter both Student ID and Order Date.")
            return
        c = self.app.db.conn.cursor()
        c.execute("SELECT 1 FROM students WHERE student_id=?", (sid,))
        if not c.fetchone():
            messagebox.showerror("Invalid student", f"No registered student with ID '{sid}'.")
            return
        try:
            datetime.strptime(odate, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Invalid date", "Date must be in YYYY-MM-DD format.")
            return

        self.refresh_meal_options()
        c.execute(
            "SELECT order_id, status FROM orders WHERE student_id=? AND order_date=?",
            (sid, odate),
        )
        row = c.fetchone()
        self.order_items = []
        if row:
            self.current_order_id, status = row
            if status == "cancelled":
                messagebox.showinfo(
                    "Cancelled order", "This order was previously cancelled. Saving will reactivate it."
                )
            c.execute(
                """SELECT m.meal_id, m.name, oi.quantity
                   FROM order_items oi JOIN meals m ON oi.meal_id = m.meal_id
                   WHERE oi.order_id=?""",
                (self.current_order_id,),
            )
            for mid, name, qty in c.fetchall():
                self.order_items.append((mid, name, qty))
            messagebox.showinfo("Order loaded", f"Existing order #{self.current_order_id} loaded for editing.")
        else:
            self.current_order_id = None
            messagebox.showinfo("New order", "No existing order found. Starting a new one.")
        self.refresh_items_tree()

    def add_item(self):
        if self.student_entry.get().strip() == "" or self.date_entry.get().strip() == "":
            messagebox.showerror("No order", "Load or start an order first.")
            return
        label = self.meal_combo.get()
        if not label or label not in self.meal_map:
            messagebox.showerror("Missing meal", "Select a meal from the list.")
            return
        qty_str = self.qty_entry.get().strip()
        if not qty_str.isdigit() or int(qty_str) <= 0:
            messagebox.showerror("Invalid quantity", "Quantity must be a positive whole number.")
            return
        qty = int(qty_str)
        meal_id = self.meal_map[label]
        meal_name = label

        for i, (mid, name, q) in enumerate(self.order_items):
            if mid == meal_id:
                self.order_items[i] = (mid, name, q + qty)
                break
        else:
            self.order_items.append((meal_id, meal_name, qty))

        self.refresh_items_tree()

    def remove_item(self):
        sel = self.items_tree.selection()
        if not sel:
            return
        idx = self.items_tree.index(sel[0])
        del self.order_items[idx]
        self.refresh_items_tree()

    def refresh_items_tree(self):
        for row in self.items_tree.get_children():
            self.items_tree.delete(row)
        for mid, name, qty in self.order_items:
            self.items_tree.insert("", "end", values=(name, qty))

    def save_order(self):
        sid = self.student_entry.get().strip()
        odate = self.date_entry.get().strip()
        if not sid or not odate:
            messagebox.showerror("Missing field", "Enter both Student ID and Order Date.")
            return
        if not self.order_items:
            messagebox.showerror("Empty order", "Add at least one meal before saving.")
            return

        c = self.app.db.conn.cursor()
        if self.current_order_id is None:
            c.execute(
                "INSERT INTO orders (student_id, order_date, status) VALUES (?,?,'active')",
                (sid, odate),
            )
            self.current_order_id = c.lastrowid
        else:
            c.execute(
                "UPDATE orders SET status='active' WHERE order_id=?", (self.current_order_id,)
            )
            c.execute("DELETE FROM order_items WHERE order_id=?", (self.current_order_id,))

        for mid, name, qty in self.order_items:
            c.execute(
                "INSERT INTO order_items (order_id, meal_id, quantity) VALUES (?,?,?)",
                (self.current_order_id, mid, qty),
            )
        self.app.db.conn.commit()
        messagebox.showinfo("Saved", f"Order #{self.current_order_id} saved. Totals updated.")

    def cancel_order(self):
        if self.current_order_id is None:
            messagebox.showerror("No order", "Load an existing order first.")
            return
        if not messagebox.askyesno("Confirm", "Cancel this order? Totals will be updated."):
            return
        c = self.app.db.conn.cursor()
        c.execute("UPDATE orders SET status='cancelled' WHERE order_id=?", (self.current_order_id,))
        self.app.db.conn.commit()
        messagebox.showinfo("Cancelled", "Order cancelled. Daily totals updated.")
        self.order_items = []
        self.current_order_id = None
        self.refresh_items_tree()

    def search_orders(self):
        sid = self.search_entry.get().strip()
        for row in self.results_tree.get_children():
            self.results_tree.delete(row)
        c = self.app.db.conn.cursor()
        if sid:
            c.execute(
                "SELECT order_id, student_id, order_date, status FROM orders WHERE student_id=? ORDER BY order_date DESC",
                (sid,),
            )
        else:
            c.execute("SELECT order_id, student_id, order_date, status FROM orders ORDER BY order_date DESC")
        for row in c.fetchall():
            self.results_tree.insert("", "end", values=row)


# ----------------------------------------------------------------------------
# PREPARATION TAB (Success criterion 8, plus CSV export)
# ----------------------------------------------------------------------------
class PreparationTab(tk.Frame):
    def __init__(self, parent, app: CanteenApp):
        super().__init__(parent)
        self.app = app

        top = tk.Frame(self)
        top.pack(fill="x", padx=10, pady=10)

        tk.Label(top, text="Date (YYYY-MM-DD):").pack(side="left", padx=5)
        self.date_entry = tk.Entry(top, width=15)
        self.date_entry.insert(0, date.today().isoformat())
        self.date_entry.pack(side="left", padx=5)

        tk.Button(top, text="View Preparation Totals", command=self.view_totals).pack(side="left", padx=10)
        tk.Button(top, text="Export Preparation List (CSV)", command=self.export_csv).pack(side="left", padx=10)

        self.tree = ttk.Treeview(self, columns=("meal", "portions"), show="headings", height=20)
        self.tree.heading("meal", text="Meal")
        self.tree.heading("portions", text="Portions Required")
        self.tree.column("meal", width=400)
        self.tree.column("portions", width=150)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

    def get_totals(self, target_date):
        c = self.app.db.conn.cursor()
        c.execute(
            """SELECT m.name, SUM(oi.quantity) as total
               FROM order_items oi
               JOIN orders o ON oi.order_id = o.order_id
               JOIN meals m ON oi.meal_id = m.meal_id
               WHERE o.order_date=? AND o.status='active'
               GROUP BY m.meal_id
               ORDER BY m.name""",
            (target_date,),
        )
        return c.fetchall()

    def view_totals(self):
        target_date = self.date_entry.get().strip()
        try:
            datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Invalid date", "Date must be in YYYY-MM-DD format.")
            return
        for row in self.tree.get_children():
            self.tree.delete(row)
        results = self.get_totals(target_date)
        if not results:
            messagebox.showinfo("No orders", "No active orders found for this date.")
            return
        for name, total in results:
            self.tree.insert("", "end", values=(name, total))

    def export_csv(self):
        target_date = self.date_entry.get().strip()
        try:
            datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Invalid date", "Date must be in YYYY-MM-DD format.")
            return
        results = self.get_totals(target_date)
        if not results:
            messagebox.showinfo("No orders", "No active orders found for this date.")
            return
        filename = f"preparation_list_{target_date}.csv"
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Meal", "Portions Required"])
            writer.writerows(results)
        messagebox.showinfo("Exported", f"Preparation list exported to '{filename}'.")


# ----------------------------------------------------------------------------
# REPORTS TAB (Success criteria 9, 11)
# ----------------------------------------------------------------------------
class ReportsTab(tk.Frame):
    def __init__(self, parent, app: CanteenApp):
        super().__init__(parent)
        self.app = app

        top = tk.Frame(self)
        top.pack(fill="x", padx=10, pady=10)

        tk.Label(top, text="Month (YYYY-MM):").pack(side="left", padx=5)
        self.month_entry = tk.Entry(top, width=10)
        self.month_entry.insert(0, date.today().strftime("%Y-%m"))
        self.month_entry.pack(side="left", padx=5)

        tk.Button(top, text="Generate Popularity Report", command=self.popularity_report).pack(side="left", padx=10)
        tk.Button(top, text="Generate Financial Report", command=self.financial_report).pack(side="left", padx=10)

        self.pop_tree = ttk.Treeview(self, columns=("rank", "meal", "total_qty"), show="headings", height=10)
        self.pop_tree.heading("rank", text="Rank")
        self.pop_tree.heading("meal", text="Meal")
        self.pop_tree.heading("total_qty", text="Total Quantity Ordered")
        self.pop_tree.column("rank", width=60)
        self.pop_tree.column("meal", width=350)
        self.pop_tree.column("total_qty", width=180)
        self.pop_tree.pack(fill="both", expand=True, padx=10, pady=5)

        self.financial_label = tk.Label(self, text="", font=("Segoe UI", 11), justify="left")
        self.financial_label.pack(fill="x", padx=10, pady=10)

    def validate_month(self):
        month = self.month_entry.get().strip()
        try:
            datetime.strptime(month, "%Y-%m")
        except ValueError:
            messagebox.showerror("Invalid month", "Month must be in YYYY-MM format.")
            return None
        return month

    def popularity_report(self):
        month = self.validate_month()
        if not month:
            return
        for row in self.pop_tree.get_children():
            self.pop_tree.delete(row)
        c = self.app.db.conn.cursor()
        c.execute(
            """SELECT m.name, SUM(oi.quantity) as total
               FROM order_items oi
               JOIN orders o ON oi.order_id = o.order_id
               JOIN meals m ON oi.meal_id = m.meal_id
               WHERE o.status='active' AND strftime('%Y-%m', o.order_date) = ?
               GROUP BY m.meal_id
               ORDER BY total DESC""",
            (month,),
        )
        results = c.fetchall()
        if not results:
            messagebox.showinfo("No data", "No active orders found for this month.")
            return
        for i, (name, total) in enumerate(results, start=1):
            self.pop_tree.insert("", "end", values=(i, name, total))

    def financial_report(self):
        month = self.validate_month()
        if not month:
            return
        c = self.app.db.conn.cursor()
        c.execute(
            """SELECT SUM(oi.quantity * m.selling_price), SUM(oi.quantity * m.prep_cost)
               FROM order_items oi
               JOIN orders o ON oi.order_id = o.order_id
               JOIN meals m ON oi.meal_id = m.meal_id
               WHERE o.status='active' AND strftime('%Y-%m', o.order_date) = ?""",
            (month,),
        )
        revenue, cost = c.fetchone()
        revenue = revenue or 0.0
        cost = cost or 0.0
        profit = revenue - cost
        self.financial_label.config(
            text=(
                f"Month: {month}\n"
                f"Estimated Revenue: {revenue:.2f}\n"
                f"Estimated Preparation Cost: {cost:.2f}\n"
                f"Estimated Gross Profit: {profit:.2f}\n"
                f"(Cancelled orders excluded)"
            )
        )


# ----------------------------------------------------------------------------
# STAFF TAB (Success criteria 10, 12) - manager only
# ----------------------------------------------------------------------------
class StaffTab(tk.Frame):
    def __init__(self, parent, app: CanteenApp):
        super().__init__(parent)
        self.app = app

        form = tk.LabelFrame(self, text="Create Staff Account")
        form.pack(fill="x", padx=10, pady=10)

        tk.Label(form, text="Username:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.username_entry = tk.Entry(form)
        self.username_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(form, text="Password:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.password_entry = tk.Entry(form, show="*")
        self.password_entry.grid(row=0, column=3, padx=5, pady=5)

        tk.Label(form, text="Role:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.role_combo = ttk.Combobox(form, values=["staff", "manager"], state="readonly")
        self.role_combo.set("staff")
        self.role_combo.grid(row=1, column=1, padx=5, pady=5)

        tk.Button(form, text="Create Account", command=self.create_account).grid(
            row=1, column=3, padx=5, pady=5
        )

        self.tree = ttk.Treeview(self, columns=("username", "role", "active"), show="headings", height=15)
        self.tree.heading("username", text="Username")
        self.tree.heading("role", text="Role")
        self.tree.heading("active", text="Active")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        btns = tk.Frame(self)
        btns.pack(pady=5)
        tk.Button(btns, text="Deactivate Selected", command=self.deactivate_account).pack(side="left", padx=5)
        tk.Button(btns, text="Reactivate Selected", command=self.reactivate_account).pack(side="left", padx=5)

        self.refresh_list()

    def create_account(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        role = self.role_combo.get()
        if not username or not password:
            messagebox.showerror("Missing field", "Username and password are required.")
            return
        c = self.app.db.conn.cursor()
        c.execute("SELECT 1 FROM staff WHERE username=?", (username,))
        if c.fetchone():
            messagebox.showerror("Duplicate", f"Username '{username}' already exists.")
            return
        c.execute(
            "INSERT INTO staff (username, password_hash, role, active) VALUES (?,?,?,1)",
            (username, hash_password(password), role),
        )
        self.app.db.conn.commit()
        messagebox.showinfo("Success", "Staff account created.")
        self.username_entry.delete(0, tk.END)
        self.password_entry.delete(0, tk.END)
        self.refresh_list()

    def deactivate_account(self):
        sel = self.tree.selection()
        if not sel:
            return
        username = self.tree.item(sel[0], "values")[0]
        if username == self.app.current_user[0]:
            messagebox.showerror("Not allowed", "You cannot deactivate your own account.")
            return
        c = self.app.db.conn.cursor()
        c.execute("UPDATE staff SET active=0 WHERE username=?", (username,))
        self.app.db.conn.commit()
        self.refresh_list()

    def reactivate_account(self):
        sel = self.tree.selection()
        if not sel:
            return
        username = self.tree.item(sel[0], "values")[0]
        c = self.app.db.conn.cursor()
        c.execute("UPDATE staff SET active=1 WHERE username=?", (username,))
        self.app.db.conn.commit()
        self.refresh_list()

    def refresh_list(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        c = self.app.db.conn.cursor()
        c.execute("SELECT username, role, active FROM staff ORDER BY username")
        for username, role, active in c.fetchall():
            self.tree.insert("", "end", values=(username, role, "Yes" if active else "No"))


# ----------------------------------------------------------------------------
# ENTRY POINT
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    app = CanteenApp()
    app.mainloop()