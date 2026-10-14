import json, sqlite3, os
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).parent
DB = ROOT / 'qingquan.db'

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init():
    con = db(); cur = con.cursor()
    cur.executescript('''
      CREATE TABLE IF NOT EXISTS meals (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, emoji TEXT, description TEXT, tags TEXT, service_date TEXT, cutoff TEXT, active INTEGER DEFAULT 1);
      CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_name TEXT NOT NULL, service_date TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS order_items (id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL, meal_id INTEGER NOT NULL, meal_name TEXT NOT NULL, quantity INTEGER NOT NULL);
    ''')
    if cur.execute('SELECT COUNT(*) FROM meals').fetchone()[0] == 0:
        seed=[('香煎檸檬雞腿飯','🍗','嫩煎雞腿・季節時蔬・溏心蛋','人氣,含蛋'),('田園蔬食藜麥碗','🥬','藜麥・烤時蔬・胡麻醬','蔬食,低負擔'),('日式味噌鯖魚便當','🐟','味噌鯖魚・玉子燒・毛豆','海鮮,含蛋')]
        cur.executemany('INSERT INTO meals(name,emoji,description,tags,service_date,cutoff) VALUES(?,?,?,?,?,?)',[(n,e,d,t,'2026-10-14','10:30') for n,e,d,t in seed])
    con.commit(); con.close()

class Handler(SimpleHTTPRequestHandler):
    def row_dict(self, row): return {key: row[key] for key in row.keys()}
    def send_json(self, data, status=200):
        raw=json.dumps(data,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def read_json(self): return json.loads(self.rfile.read(int(self.headers.get('Content-Length','0')) or 0) or '{}')
    def do_GET(self):
        path=urlparse(self.path)
        if path.path=='/api/menu':
            con=db(); rows=con.execute('SELECT id,name,emoji,description AS desc,tags FROM meals WHERE active=1 ORDER BY id').fetchall(); con.close()
            self.send_json([{**self.row_dict(r), 'tags': r['tags'].split(',')} for r in rows]); return
        if path.path=='/api/orders':
            user=parse_qs(path.query).get('user',['obgs'])[0]; con=db(); orders=[]
            for o in con.execute('SELECT * FROM orders WHERE user_name=? ORDER BY id DESC',(user,)).fetchall():
                items=[{'name':x['meal_name'],'qty':x['quantity']} for x in con.execute('SELECT meal_name,quantity FROM order_items WHERE order_id=?',(o['id'],))]
                orders.append({'id':o['id'],'date':o['service_date'],'items':items,'status':o['status']})
            con.close(); self.send_json(orders); return
        return super().do_GET()
    def do_POST(self):
        path=urlparse(self.path).path; data=self.read_json(); con=db()
        if path=='/api/orders':
            cur=con.execute('INSERT INTO orders(user_name,service_date,status,created_at) VALUES(?,?,?,?)',(data.get('user','obgs'),data.get('date','2026-10-14'),'已送出',datetime.now().isoformat(timespec='seconds'))); oid=cur.lastrowid
            con.executemany('INSERT INTO order_items(order_id,meal_id,meal_name,quantity) VALUES(?,?,?,?)',[(oid,x.get('meal_id',0),x['name'],x['qty']) for x in data.get('items',[])]); con.commit(); con.close(); self.send_json({'id':oid},201); return
        if path=='/api/meals':
            con.execute('INSERT INTO meals(name,emoji,description,tags,service_date,cutoff) VALUES(?,?,?,?,?,?)',(data['name'],data.get('emoji','🍱'),data.get('desc',''),','.join(data.get('tags',[])),'2026-10-14','10:30')); con.commit(); rows=con.execute('SELECT id,name,emoji,description AS desc,tags FROM meals WHERE active=1 ORDER BY id').fetchall(); con.close(); self.send_json([{**self.row_dict(r), 'tags': r['tags'].split(',')} for r in rows],201); return
        self.send_error(404)
    def do_DELETE(self):
        path=urlparse(self.path).path
        if path.startswith('/api/orders/'):
            oid=path.rsplit('/',1)[-1]; con=db(); con.execute('DELETE FROM order_items WHERE order_id=?',(oid,)); con.execute('DELETE FROM orders WHERE id=?',(oid,)); con.commit(); con.close(); self.send_json({'ok':True}); return
        self.send_error(404)

if __name__=='__main__':
    os.chdir(ROOT); init(); print('清泉中餐吧 running at http://localhost:8000'); ThreadingHTTPServer(('localhost',8000),Handler).serve_forever()
