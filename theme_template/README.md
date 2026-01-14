# Flask Web App Template (PRISM Style)

This is a reusable template for Flask-based web applications, extracting the clean, professional style used in PRISM Studio. It uses **Bootstrap 5**, **Font Awesome**, and custom CSS components designed for research tools.

## Structure
- `app.py`: Main Flask entry point using `waitress` as the production-ready server.
- `static/`: Contains CSS and images.
- `templates/`: Contains Jinja2 templates.
    - `base.html`: The core layout (navbar, footer, dependencies).
    - `index.html`: A sample page showing available UI components.

## UI Components Included
1.  **Feature Cards**: Card-based layout with soft shadows and hover effects (`.feature-card`).
2.  **Upload Area**: A stylized drag-and-drop zone (`.upload-area`).
3.  **Status Items**: Color-coded blocks for errors and warnings (`.error-item`, `.warning-item`).
4.  **Responsive Layout**: Optimized for various screen sizes using Bootstrap 5.
5.  **Auto-Shutdown**: Integrated "Quit" functionality for desktop-like local web apps.

## How to use in a new repo
1.  Copy the `static/`, `templates/` and `app.py` to your new repository.
2.  Install dependencies:
    ```bash
    pip install flask waitress
    ```
3.  Customize `base.html`:
    - Replace the logo in `static/img/logo.png`.
    - Update project names and links in the navbar and footer.
4.  Run your app:
    ```bash
    python app.py
    ```

## Integration with Waitress
The `app.py` is configured to run on `127.0.0.1:5001` and automatically opens your default web browser on startup, making it feel like a desktop application.
