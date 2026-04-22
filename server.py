#!/usr/bin/env python3
"""
Simple Web Server for Trump Tweet Analyzer Dashboard
Serves the dashboard and provides API endpoints for data

Usage:
  python server.py
  Then open: http://localhost:8888
"""

import json
import http.server
import socketserver
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urlparse

BASE = Path(__file__).parent
DATA = BASE / "data"
PORT = 8888


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler for dashboard requests"""

    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)

        # Serve dashboard at root
        if parsed_path.path == '/' or parsed_path.path == '/index.html':
            self.serve_file('dashboard.html', 'text/html')

        # API endpoint for dashboard data
        elif parsed_path.path == '/api/dashboard':
            self.serve_dashboard_data()

        # Let parent class handle other files
        else:
            super().do_GET()

    def serve_file(self, filename, content_type):
        """Serve a file with given content type"""
        try:
            filepath = BASE / filename
            with open(filepath, 'rb') as f:
                content = f.read()

            self.send_response(200)
            self.send_header('Content-type', content_type)
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error serving file: {e}")

    def serve_dashboard_data(self):
        """Serve JSON data for the dashboard"""
        try:
            data = self.collect_dashboard_data()
            json_data = json.dumps(data, indent=2).encode('utf-8')

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Content-Length', len(json_data))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json_data)
        except Exception as e:
            self.send_error(500, f"Error collecting data: {e}")

    def collect_dashboard_data(self):
        """Collect all data needed for dashboard"""

        # Load latest posts
        latest_posts = self.load_latest_posts()

        # Classify signals for each post
        for post in latest_posts:
            if 'signals' not in post:
                post['signals'] = self.classify_post_signals(post.get('content', ''))

        # Get today's signals
        signals_today = self.get_signals_today(latest_posts)

        # Get entity mentions (last 7 days)
        entity_mentions = self.get_entity_mentions(latest_posts)

        # Get prediction
        prediction = self.get_latest_prediction()

        return {
            'total_posts': len(latest_posts),
            'latest_posts': latest_posts[:10],  # Last 10 posts
            'signals_today': signals_today,
            'entity_mentions': entity_mentions,
            'prediction': prediction,
            'last_updated': datetime.utcnow().isoformat()
        }

    def classify_post_signals(self, content):
        """Classify signals in a post"""
        cl = content.lower()
        signals = []

        # Policy signals
        if any(w in cl for w in ['tariff', 'tariffs', 'duty', 'duties', 'reciprocal']):
            signals.append('TARIFF')
        if any(w in cl for w in ['deal', 'agreement', 'negotiate', 'talks', 'signed']):
            signals.append('DEAL')
        if any(w in cl for w in ['pause', 'delay', 'exempt', 'exception', 'suspend', 'postpone']):
            signals.append('RELIEF')
        if any(w in cl for w in ['immediately', 'effective', 'hereby', 'executive order', 'just signed']):
            signals.append('ACTION')

        # Country mentions
        if any(w in cl for w in ['iran', 'iranian', 'tehran']):
            signals.append('IRAN')
        if any(w in cl for w in ['china', 'chinese', 'beijing']):
            signals.append('CHINA')
        if any(w in cl for w in ['russia', 'russian', 'putin']):
            signals.append('RUSSIA')
        if any(w in cl for w in ['mexico', 'mexican']):
            signals.append('MEXICO')

        return signals

    def load_latest_posts(self):
        """Load latest Trump posts from data files"""
        posts = []

        # Try trump_posts_all.json first
        posts_file = DATA / "trump_posts_all.json"
        if posts_file.exists():
            try:
                with open(posts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and 'posts' in data:
                        posts = data['posts']
                    elif isinstance(data, list):
                        posts = data
            except:
                pass

        # Try predictions_log.json as fallback
        if not posts:
            pred_file = DATA / "predictions_log.json"
            if pred_file.exists():
                try:
                    with open(pred_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            posts = [p for p in data if 'content' in p]
                except:
                    pass

        # Sort by created_at (newest first)
        if posts:
            posts.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        return posts

    def get_signals_today(self, posts):
        """Count signals detected on the most recent day in data"""
        from collections import Counter
        signals = Counter()

        # Get the most recent date in the posts
        if not posts or len(posts) == 0:
            return {}

        latest_date = None
        try:
            latest_date_str = posts[0].get('created_at', '')
            latest_date = datetime.fromisoformat(latest_date_str.replace('Z', '+00:00')).date()
        except:
            return {}

        # Count signals from that day
        for post in posts:
            post_date_str = post.get('created_at', '')
            if post_date_str:
                try:
                    post_date = datetime.fromisoformat(post_date_str.replace('Z', '+00:00')).date()
                    if post_date == latest_date:
                        for signal in post.get('signals', []):
                            signals[signal] += 1
                except:
                    pass

        return dict(signals)

    def get_entity_mentions(self, posts):
        """Count entity mentions in last 7 days from most recent post"""
        from collections import Counter
        entities = Counter()

        # Get cutoff date from most recent post
        if not posts or len(posts) == 0:
            return {}

        try:
            latest_date_str = posts[0].get('created_at', '')
            latest_date = datetime.fromisoformat(latest_date_str.replace('Z', '+00:00'))
            cutoff = latest_date - timedelta(days=7)
        except:
            cutoff = datetime.utcnow() - timedelta(days=7)

        # Entity keywords
        entity_map = {
            'China': ['china', 'chinese', 'beijing', 'xi'],
            'Iran': ['iran', 'iranian', 'tehran'],
            'Russia': ['russia', 'russian', 'putin'],
            'Mexico': ['mexico', 'mexican'],
            'Canada': ['canada', 'canadian', 'trudeau'],
            'Israel': ['israel', 'israeli', 'netanyahu'],
            'Ukraine': ['ukraine', 'ukrainian', 'zelensky'],
        }

        for post in posts:
            post_date_str = post.get('created_at', '')
            content = post.get('content', '').lower()

            if post_date_str and content:
                try:
                    post_date = datetime.fromisoformat(post_date_str.replace('Z', '+00:00'))
                    if post_date >= cutoff:
                        for entity, keywords in entity_map.items():
                            if any(kw in content for kw in keywords):
                                entities[entity] += 1
                except:
                    pass

        return dict(entities)

    def get_latest_prediction(self):
        """Get latest market prediction"""
        pred_file = DATA / "predictions_log.json"

        if pred_file.exists():
            try:
                with open(pred_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        # Get most recent prediction
                        latest = data[-1]
                        return {
                            'direction': latest.get('prediction', 'NEUTRAL'),
                            'confidence': latest.get('confidence', 'Medium'),
                            'models_count': latest.get('models_count', 0)
                        }
            except:
                pass

        return {'direction': 'NEUTRAL', 'confidence': 'N/A', 'models_count': 0}

    def log_message(self, format, *args):
        """Custom log format"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {format % args}")


def main():
    """Start the web server"""
    handler = DashboardHandler

    print("=" * 60)
    print("  Trump Tweet Analyzer Dashboard Server")
    print("  ECE 110 Project")
    print("=" * 60)
    print(f"\n  Server starting on port {PORT}...")
    print(f"\n  Open your browser to:")
    print(f"  > http://localhost:{PORT}")
    print(f"\n  Press Ctrl+C to stop\n")

    with socketserver.TCPServer(("", PORT), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n  Server stopped. Goodbye!")


if __name__ == '__main__':
    main()

