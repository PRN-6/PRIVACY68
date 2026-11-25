"""A compact text command entry window with asynchronous execution."""

import logging
import queue
import threading
import tkinter as tk

logger = logging.getLogger("PRIVACY68.CommandBar")


class CommandBar:
    def __init__(self, parent_root):
        self.is_processing = False
        self._results = queue.Queue()
        self._drag_origin = (0, 0)
        self.window = tk.Toplevel(parent_root)
        self.window.title("PRIVACY68 Quick Command")
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg="#0d111a")
        width, height = 480, 190
        x = max(20, (parent_root.winfo_screenwidth() - width) // 2)
        y = max(20, parent_root.winfo_screenheight() - height - 100)
        self.window.geometry(f"{width}x{height}+{x}+{y}")

        header = tk.Frame(self.window, bg="#1e293b", padx=12, pady=8)
        header.pack(fill="x")
        title = tk.Label(header, text="PRIVACY68 // QUICK COMMAND", bg="#1e293b",
                         fg="#cbd5e1", font=("Segoe UI", 9, "bold"))
        title.pack(side="left")
        tk.Button(header, text="✕", command=self.hide, bg="#1e293b", fg="#cbd5e1",
                  relief="flat", cursor="hand2").pack(side="right")
        for widget in (header, title):
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)

        self.status = tk.Label(self.window, text="Type a command • Enter to run • Esc to hide",
                               bg="#0d111a", fg="#94a3b8", anchor="w", justify="left",
                               wraplength=450, font=("Segoe UI", 9))
        self.status.pack(fill="x", padx=14, pady=12)
        row = tk.Frame(self.window, bg="#0d111a")
        row.pack(side="bottom", fill="x", padx=14, pady=14)
        self.cmd_entry = tk.Entry(row, bg="#0f172a", fg="#f1f5f9", insertbackground="#38bdf8",
                                  relief="flat", font=("Segoe UI", 11))
        self.cmd_entry.pack(side="left", fill="x", expand=True, ipady=7)
        self.send_btn = tk.Button(row, text="Run ↵", command=self._on_text_submitted,
                                  bg="#2563eb", fg="white", relief="flat", padx=12, pady=5)
        self.send_btn.pack(side="right", padx=(8, 0))
        self.cmd_entry.bind("<Return>", lambda event: self._on_text_submitted())
        self.window.bind("<Escape>", lambda event: self.hide())
        self.window.protocol("WM_DELETE_WINDOW", self.hide)
        self._poll_job = self.window.after(50, self._poll_results)
        self.window.bind("<Destroy>", self._on_destroy)

    def _start_drag(self, event):
        self._drag_origin = (event.x_root - self.window.winfo_x(), event.y_root - self.window.winfo_y())

    def _drag(self, event):
        x, y = self._drag_origin
        self.window.geometry(f"+{event.x_root - x}+{event.y_root - y}")

    def is_alive(self):
        try:
            return bool(self.window.winfo_exists())
        except tk.TclError:
            return False

    def show(self):
        self.window.deiconify()
        self.window.lift()
        self.cmd_entry.focus_set()

    def hide(self):
        self.window.withdraw()

    def toggle(self):
        if self.window.state() == "withdrawn":
            self.show()
        else:
            self.hide()

    def _on_text_submitted(self):
        command = self.cmd_entry.get().strip()
        if self.is_processing or not command:
            return
        self.is_processing = True
        self.send_btn.configure(state="disabled")
        self.status.configure(text="Running command…", fg="#c084fc")
        self.cmd_entry.delete(0, tk.END)
        threading.Thread(target=self._execute, args=(command,), daemon=True).start()

    def _execute(self, command):
        """Workers only touch the queue, never Tk widgets or Tk.after()."""
        try:
            from actions.executor import execute_system_command_detailed
            result = execute_system_command_detailed(command)
            success = bool(result.get("success"))
            message = str(result.get("output") or result.get("message") or "Completed.")
        except Exception as error:
            logger.exception("Command execution failed")
            success, message = False, str(error)
        self._results.put((success, message))

    def _poll_results(self):
        try:
            success, message = self._results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.is_processing = False
            self.send_btn.configure(state="normal")
            self.status.configure(text=message[:240], fg="#10b981" if success else "#f87171")
        self._poll_job = self.window.after(50, self._poll_results)

    def _on_destroy(self, event):
        if event.widget == self.window and self._poll_job:
            self.window.after_cancel(self._poll_job)
            self._poll_job = None
