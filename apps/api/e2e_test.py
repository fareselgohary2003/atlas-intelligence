import requests, sys, time

BASE = 'http://localhost:8001'
H = {'Origin': 'http://localhost:3001', 'Content-Type': 'application/json'}
s = requests.Session()

print('[1] HEALTH:', s.get(BASE+'/api/health').json())

r = s.post(BASE+'/api/auth/login', json={'email':'fareselgohary2003@gmail.com','password':'fares1234'}, headers=H)
print('[2] LOGIN: HTTP', r.status_code, r.json().get('user',{}).get('email'))
csrf = s.cookies.get('atlas_csrf','')
print('    CSRF:', bool(csrf))
if r.status_code != 200: sys.exit('login fail')

me = s.get(BASE+'/api/auth/me', headers=H).json()
wid = me['workspaces'][0]['id']
print('[3] WORKSPACE:', me['workspaces'][0]['name'], 'id='+wid)

csrfH = {**H, 'X-CSRF-Token': csrf}
r = s.post(BASE+'/api/research',
           json={'workspace_id':wid,'title':'AI in MENA FinTech 2023-2025',
                 'objective':'What are AI and FinTech trends in MENA 2023-2025?',
                 'geography':'Middle East and North Africa','sector':'FinTech','depth':'deep'},
           headers=csrfH)
print('[4] CREATE RESEARCH: HTTP', r.status_code)
rid = r.json()['id']
print('    Research ID:', rid)

r = s.post(BASE+'/api/research/'+rid+'/runs', json={}, headers=csrfH)
print('[5] START RUN: HTTP', r.status_code, 'status='+r.json().get('status','?'))

for i in range(1, 14):
    time.sleep(5)
    st = s.get(BASE+'/api/research/'+rid+'/status', headers=H).json()
    print('[6.'+str(i).zfill(2)+']', str(i*5)+'s status='+str(st.get('status'))+' phase='+str(st.get('phase')))
    if st.get('status') in ('done','failed','cancelled'): break

r = s.get(BASE+'/api/research/'+rid+'/report/versions', headers=H)
vers = r.json() if r.status_code==200 else []
print('[7] VERSIONS:', len(vers))
if vers:
    rv = vers[0]['version']
    rep = s.get(BASE+'/api/research/'+rid+'/report?version='+str(rv), headers=H).json()
    st2 = rep.get('stats',{})
    bg = st2.get('by_group',{})
    print('    claims='+str(st2.get('claims',0))+' verified='+str(st2.get('verified',0))+' partial='+str(bg.get('partial',0))+' sources='+str(st2.get('sources',0)))
    print('    sections='+str(len(rep.get('sections',[]))))

print()
print('==> http://localhost:3001/research/'+rid)
print('Untrusted origin: FIXED')
print('Research: SUBMITTED')
print('Report: '+('GENERATED' if vers else 'PENDING'))
