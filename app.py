import requests
from flask import Flask, render_template, abort
from config import Config
import time
from threading import Lock

app = Flask(__name__)
app.config.from_object(Config)

# 获取飞书 tenant_access_token（每次请求动态获取）
def get_feishu_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
    payload = {
        "app_id": app.config["FEISHU_APP_ID"],
        "app_secret": app.config["FEISHU_APP_SECRET"]
    }
    resp = requests.post(url, json=payload)
    data = resp.json()
    if data.get("code") == 0:
        return data["tenant_access_token"]
    else:
        raise Exception(f"获取飞书token失败: {data}")

# 获取多维表格数据
def get_bitable_records():
    token = get_feishu_token()
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app.config['BASE_ID']}/tables/{app.config['TABLE_ID']}/records"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    data = resp.json()
    if data.get("code") == 0:
        return data["data"]["items"]
    else:
        raise Exception(f"获取多维表格数据失败: {data}")

# 简单内存缓存
_cache = {
    'data': None,
    'timestamp': 0
}
_cache_lock = Lock()
CACHE_TTL = 60  # 缓存60秒

def get_bitable_records_cached():
    now = time.time()
    with _cache_lock:
        if _cache['data'] is not None and now - _cache['timestamp'] < CACHE_TTL:
            return _cache['data']
        # 否则重新获取
        data = get_bitable_records()
        _cache['data'] = data
        _cache['timestamp'] = now
        return data

def extract_text(field):
    if isinstance(field, list):
        # 飞书富文本字段通常为 [{'text': '内容', ...}, ...]
        return ''.join([item.get('text', '') for item in field if isinstance(item, dict)])
    elif isinstance(field, dict):
        return field.get('text', '')
    elif field is None:
        return ''
    return str(field)

# 首页
@app.route('/')
def index():
    try:
        records = get_bitable_records_cached()
        articles = []
        for r in records:
            fields = r.get('fields', {})
            articles.append({
                'id': r.get('record_id'),
                'title': extract_text(fields.get('标题', '')),
                'quote': extract_text(fields.get('金句输出', '')),
                'comment': extract_text(fields.get('黄叔点评', '')),
                'summary': extract_text(fields.get('概要内容输出', ''))[:100],
                'full_summary': extract_text(fields.get('概要内容输出', '')),
                'origin_url': extract_text(fields.get('链接', '')),
            })
        return render_template('index.html', articles=articles)
    except Exception as e:
        return f"数据获取失败: {e}", 500

# 详情页
@app.route('/detail/<record_id>')
def detail(record_id):
    try:
        records = get_bitable_records_cached()
        article = None
        for r in records:
            if r.get('record_id') == record_id:
                fields = r.get('fields', {})
                article = {
                    'id': r.get('record_id'),
                    'title': extract_text(fields.get('标题', '')),
                    'quote': extract_text(fields.get('金句输出', '')),
                    'comment': extract_text(fields.get('黄叔点评', '')),
                    'content': extract_text(fields.get('概要内容输出', '')),
                    'origin_url': extract_text(fields.get('链接', '')),
                }
                break
        if not article:
            abort(404)
        return render_template('detail.html', article=article)
    except Exception as e:
        return f"数据获取失败: {e}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)