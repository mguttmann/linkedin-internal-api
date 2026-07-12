#!/usr/bin/env python3
"""post_final.py — Complete post flow, atomic, purely coordinate-based (bypasses
iframe/shadow-DOM). Opens the sharebox, clicks the text field, types a marker, clicks Post.
Screenshots + network log for verification. Prints the create request + URN.
"""
import json, urllib.request, websocket, time, sys, os, base64

def wsc():
    t = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json/list'))
    t = [x for x in t if x.get('type') == 'page'][0]
    return websocket.create_connection(t['webSocketDebuggerUrl'], timeout=60, origin='http://127.0.0.1:9222', max_size=None)

ws = wsc(); _id=[0]; reqs={}; resps={}
def call(m,p=None):
    _id[0]+=1; rid=_id[0]; ws.send(json.dumps({'id':rid,'method':m,'params':p or {}}))
    while True:
        x=json.loads(ws.recv())
        if x.get('id')==rid: return x.get('result',{})
        me=x.get('method')
        if me=='Network.requestWillBeSent':
            r=x['params']['request']
            if r.get('method') in ('POST','PUT') and ('/voyager/api/' in r['url'] or '/rsc-action/' in r['url']):
                reqs[x['params']['requestId']]={'method':r['method'],'url':r['url'],'postData':r.get('postData')}
        elif me=='Network.responseReceived':
            rid2=x['params']['requestId']
            if rid2 in reqs: resps[rid2]=x['params']['response'].get('headers',{})

def ev(js): return call('Runtime.evaluate',{'expression':js,'returnByValue':True}).get('result',{}).get('value')
def click(x,y):
    call('Input.dispatchMouseEvent',{'type':'mouseMoved','x':x,'y':y}); time.sleep(0.3)
    call('Input.dispatchMouseEvent',{'type':'mousePressed','x':x,'y':y,'button':'left','clickCount':1}); time.sleep(0.1)
    call('Input.dispatchMouseEvent',{'type':'mouseReleased','x':x,'y':y,'button':'left','clickCount':1})
def shot(name):
    r=call('Page.captureScreenshot',{'format':'png'})
    if r.get('data'): open(f'/tmp/{name}.png','wb').write(base64.b64decode(r['data']))

MARKER='apitest loeschen '+str(int(time.time()))
call('Network.enable'); call('Page.enable')
call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':900,'deviceScaleFactor':1,'mobile':False})
call('Page.navigate',{'url':'https://www.linkedin.com/feed/'}); time.sleep(11)

# Open the sharebox
coord=ev(r'''(()=>{const b=[...document.querySelectorAll('*')].find(e=>(e.innerText||'').trim()==='Beitrag beginnen');if(!b)return '';const r=b.getBoundingClientRect();return JSON.stringify({x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)});})()''')
if not coord: print("FAIL sharebox"); sys.exit(1)
c=json.loads(coord); click(c['x'],c['y'])

# Wait until the modal is visible (text "Worüber" appears) — up to 20s
opened=False
for s in range(20):
    time.sleep(1)
    txt=ev(r'''(()=>{const b=document.body.innerText;return b.includes('Worüber möchten Sie sprechen')||b.includes('What do you want to talk about')?'1':'0';})()''')
    if txt=='1': opened=True; print(f"Composer sichtbar nach {s+1}s"); break
if not opened:
    shot('no_composer'); print("FAIL: Composer-Text nie erschienen"); sys.exit(1)

# Click into the text field (top-center, where the placeholder is) + type
click(515,175); time.sleep(1)
call('Input.insertText',{'text':MARKER}); time.sleep(2)
shot('after_type')

# Check whether the Post button became active (text in field -> button enabled)
# Post button by coordinate (bottom right). Fresh network log.
reqs.clear(); resps.clear()
click(1025,592); time.sleep(6)
shot('after_post')

print(f"MARKER={MARKER}")
print(f"Create-Mutationen: {len(reqs)}")
out=[]
for rid,r in list(reqs.items()):
    h=resps.get(rid,{}); restli=h.get('X-RestLi-Id') or h.get('x-restli-id')
    print(f"\n>>> {r['method']} {r['url'][:120]}")
    if r['postData']: print(f"   BODY: {r['postData'][:600]}")
    if restli: print(f"   X-RestLi-Id: {restli}")
    r['restli']=restli; out.append(r)
os.makedirs('_writes',exist_ok=True)
json.dump(out,open('_writes/post_create_final.json','w'),ensure_ascii=False,indent=2)
ws.close()
