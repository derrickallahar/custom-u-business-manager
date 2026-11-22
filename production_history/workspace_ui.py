"""Shared interface assets for the existing authenticated application pages."""
from flask import request

PAGES = frozenset(('/', '/customers', '/quotes', '/invoices', '/payments',
    '/credits', '/statements', '/jobs', '/products', '/mockups', '/catalogues',
    '/staff', '/reminders', '/legacy-balances', '/opening-balances',
    '/customers/import', '/customers/reviewed-import', '/products/csv-import',
    '/artwork', '/email'))

def install(app, root):
    assets = {
        'workspace.css': ('workspace.css', 'text/css'),
        'workspace-shell.js': ('workspace-shell.js', 'text/javascript'),
        'brand/custom-u-logo.png': ('brand/custom-u-logo.png', 'image/png'),
    }
    @app.get('/workspace-assets/<path:name>')
    def workspace_asset(name):
        from flask import abort
        if name not in assets:
            abort(404)
        filename, mime = assets[name]
        return app.response_class((root / 'static' / filename).read_bytes(), mimetype=mime)

    @app.after_request
    def workspace_layout(response):
        if (request.path in PAGES or request.endpoint == 'artwork_page') and response.status_code == 200 and response.mimetype == 'text/html':
            html = response.get_data(as_text=True)
            additions = ('<link rel="stylesheet" href="/workspace-assets/workspace.css">'
                         '<script src="/workspace-assets/workspace-shell.js" defer></script>')
            response.set_data(html.replace('</head>', additions + '</head>', 1))
        return response
