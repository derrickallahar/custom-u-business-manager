"""Local-only artwork byte recovery. No cloud credentials, network or extractall."""
import getpass,hashlib,io,json,sys,tempfile,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'offline_recovery'))
from recover_crm import require,uid,canonical
from artwork_rules import validate_artwork
from artwork_codec import decrypt,MAX_BYTES
from backup_codec import parse

def restore(blob,password,parent):
    raw=decrypt(blob,password)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=z.namelist();require(len(names)==len(set(names)) and len(names)<=51 and 'manifest.json' in names)
        require(sum(i.file_size for i in z.infolist())<=MAX_BYTES and all(i.compress_type==zipfile.ZIP_STORED and not i.is_dir() for i in z.infolist()))
        require(z.getinfo('manifest.json').file_size<=2000000)
        m=parse(z.read('manifest.json'));require(isinstance(m,dict) and set(m)=={'format','job','files','head','audit'} and m['format']=='custom-u-artwork-bundle-104')
        j=m['job'];require(isinstance(j,dict) and set(j)=={'id','number','is_test','status','title','customer'});uid(j['id']);require(type(j['is_test']) is bool and all(isinstance(j[k],str) for k in ('number','status','title','customer')))
        validate_artwork(m['files'],[m['head']] if m['head'] else [],m['audit']);require(all(f['job_id']==j['id'] for f in m['files']) and all(a['job_id']==j['id'] for a in m['audit']) and (not m['head'] or m['head']['job_id']==j['id']))
        stored=[f for f in m['files'] if f['status']=='stored'];expected={'manifest.json'}|{'files/'+f['id']+'.'+f['filename'].rsplit('.',1)[1] for f in stored};require(set(names)==expected and stored)
        blobs={}
        for f in stored:
            name='files/'+f['id']+'.'+f['filename'].rsplit('.',1)[1];require(z.getinfo(name).file_size==f['size_bytes']);b=z.read(name);require(hashlib.sha256(b).hexdigest()==f['sha256']);blobs[name]=b
    folder=Path(tempfile.mkdtemp(prefix='CustomU_ARTWORK_RECOVERY_104_',dir=str(parent)));(folder/'files').mkdir()
    (folder/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for name,b in blobs.items():
        target=folder/name;target.write_bytes(b);require(target.read_bytes()==b)
    require(canonical(json.loads((folder/'manifest.json').read_text(encoding='utf-8')))==canonical(m))
    report={'result':'PASS','job_id':j['id'],'job_number':j['number'],'stored_files':len(stored),'pending_uploads':len(m['files'])-len(stored),'bytes_verified':sum(f['size_bytes'] for f in stored),'approved_file_id':m['head']['approved_id'] if m['head'] else None,'all_files_compared':True,'backup_sha256':hashlib.sha256(blob).hexdigest(),'unencrypted_local_files':True,'scope':'Local files only; not a cloud Storage restore'}
    (folder/'artwork_recovery_report.json').write_text(json.dumps(report,indent=2)+'\n');return folder,report

def main():
    print('CUSTOM U — LOCAL ARTWORK FILES RECOVERY CHECK 104')
    print('No cloud connections. Creates a NEW local folder containing UNENCRYPTED artwork files.')
    p=Path(input('Full path to your downloaded .cuart backup: ').strip().strip('"'));password=getpass.getpass('Backup passphrase (hidden): ')
    try:
        if p.stat().st_size>MAX_BYTES+100:raise ValueError('SIZE')
        folder,r=restore(p.read_bytes(),password,Path(__file__).resolve().parent)
        print('DECRYPT / VERSION HISTORY / FILE CHECKSUMS / LOCAL RESTORE / BYTE COMPARISON: PASS')
        print('Job:',r['job_number'],'Stored files:',r['stored_files'],'Incomplete upload records:',r['pending_uploads'])
        print('Recovery folder:',folder)
        print('Keep the encrypted .cuart and .cuwork backups, and the passphrase separately.')
        print('Remove the unencrypted recovery folder when no longer needed.')
    except Exception:print('CHECK FAILED. Check the file and passphrase. No production data was changed.');return 1
    finally:password=None
    return 0
if __name__=='__main__':sys.exit(main())
