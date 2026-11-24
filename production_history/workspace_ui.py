"""Shared interface assets for the existing authenticated application pages."""
from flask import request

PAGES = frozenset(('/', '/customers', '/quotes', '/invoices', '/payments',
    '/credits', '/statements', '/jobs', '/products', '/mockups', '/catalogues',
    '/account', '/hr', '/team', '/staff', '/admin-controls', '/reminders', '/legacy-balances', '/opening-balances',
    '/quotes/carryover', '/customers/import', '/customers/reviewed-import', '/products/csv-import', '/products/bulk-pricing',
    '/artwork', '/email'))

def install(app, root):
    assets = {
        'workspace.css': ('workspace.css', 'text/css'),
        'workspace-shell.js': ('workspace-shell.js', 'text/javascript'),
        'team-chat.js': ('team-chat.js', 'text/javascript'),
        'team-chat.css': ('team-chat.css', 'text/css'),
        'new-page.js': ('new-page.js','text/javascript'),
        'brand/custom-u-logo.png': ('brand/custom-u-logo.png', 'image/png'),
    }
    @app.get('/<feature>/new')
    def creation_page(feature):
        from flask import abort
        if feature not in ('quotes','invoices','mockups','catalogues','jobs','customers'):abort(404)
        return app.response_class((root/'static'/(feature+'.html')).read_bytes(),mimetype='text/html')

    @app.get('/workspace-assets/<path:name>')
    def workspace_asset(name):
        from flask import abort
        if name not in assets:
            abort(404)
        filename, mime = assets[name]
        return app.response_class((root / 'static' / filename).read_bytes(), mimetype=mime)

    @app.after_request
    def workspace_layout(response):
        if (request.path in PAGES or request.endpoint in ('artwork_page', 'product_detail_page','shopvox_quote_page','shopvox_invoice_page','product_group_page','creation_page')) and response.status_code == 200 and response.mimetype == 'text/html':
            html = response.get_data(as_text=True)
            additions = ('<link rel="stylesheet" href="/workspace-assets/workspace.css">'
                         '<script src="/workspace-assets/workspace-shell.js" defer></script>'
                         '<script src="/workspace-assets/new-page.js?v=117" defer></script>'
                         '<link rel="stylesheet" href="/workspace-assets/team-chat.css?v=116.1">'
                         '<script src="/workspace-assets/team-chat.js?v=116.1" defer></script>'
                         '<script src="/team-notifications.js?v=116.1" defer></script>')
            response.set_data(html.replace('</head>', additions + '</head>', 1))
        return response
