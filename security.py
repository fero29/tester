"""Prihlásenie správcu a ochrana zápisových požiadaviek."""
from collections import OrderedDict, deque
from datetime import timedelta
import hmac
import secrets
import threading
import time
from flask import abort, jsonify, redirect, render_template, request, session, url_for


class RateLimiter:
    def __init__(self):
        self.entries = OrderedDict()
        self.lock = threading.Lock()

    def allow(self, key, limit, seconds=60):
        now = time.monotonic()
        with self.lock:
            times = self.entries.setdefault(key, deque())
            self.entries.move_to_end(key)
            while times and times[0] <= now - seconds:
                times.popleft()
            while len(self.entries) > 4096:
                self.entries.popitem(last=False)
            if len(times) >= limit:
                return False
            times.append(now)
            return True


def init_security(app):
    limiter = RateLimiter()
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict',
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=8))

    def csrf_token():
        if 'csrf' not in session:
            session['csrf'] = secrets.token_urlsafe(32)
        return session['csrf']

    @app.context_processor
    def auth_context():
        return {'is_admin': bool(session.get('admin')), 'csrf_token': csrf_token}

    @app.before_request
    def guard():
        if request.method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return None
        if request.path == '/api/track':
            if not limiter.allow(('track', request.remote_addr), 120):
                return jsonify(error='Príliš veľa požiadaviek.'), 429
            return None
        # Prihlásenie je jediný zápisový endpoint dostupný neprihlásenému.
        if request.path != '/admin/login' and not session.get('admin'):
            return jsonify(error='Na úpravu testov sa prihláste ako správca.'), 401
        token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token', '')
        expected = session.get('csrf', '')
        if not expected or not hmac.compare_digest(str(token).encode('utf-8'), expected.encode('utf-8')):
            return jsonify(error='Platnosť formulára vypršala. Obnovte stránku.'), 403

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        if request.path.startswith('/admin') or request.path == '/':
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.route('/admin/login', methods=['GET', 'POST'])
    def admin_login():
        if not app.config.get('ADMIN_SECRET'):
            abort(404)
        error = None
        status = 200
        if request.method == 'POST':
            if not limiter.allow(('login', request.remote_addr), 10):
                error, status = 'Príliš veľa pokusov. Skúste to o minútu.', 429
            elif hmac.compare_digest(request.form.get('password', '').encode('utf-8'), app.config['ADMIN_SECRET'].encode('utf-8')):
                session.clear()
                session['admin'] = True
                session.permanent = True
                csrf_token()
                return redirect(url_for('index'))
            else:
                error, status = 'Nesprávne heslo.', 401
        return render_template('admin_login.html', error=error), status

    @app.post('/admin/logout')
    def admin_logout():
        session.clear()
        return redirect(url_for('index'))

    return limiter
