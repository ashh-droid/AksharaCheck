"""CLI entry point: python -m aksharacheck scan URL."""
import argparse
import asyncio
import sys
from .browser import Scanner
from .ai import explain_and_verify
from .report import write_reports


def main():
    parser=argparse.ArgumentParser(prog="aksharacheck",description="Indic text rendering checks with browser evidence")
    sub=parser.add_subparsers(dest='command',required=True)
    scan=sub.add_parser('scan',help='Scan a website using Chromium')
    scan.add_argument('url');scan.add_argument('--lang',choices=['hi','kn','both'],default='both')
    scan.add_argument('--output',default='output');scan.add_argument('--pages',type=int,default=1)
    scan.add_argument('--ai',action='store_true',help='Use BharatCode to propose and verify CSS fixes')
    scan.add_argument('--allow-local',action='store_true',help='ONLY for a trusted local test site')
    scan.add_argument('--fail-on',choices=['error','warning','never'],default='never')
    serve=sub.add_parser('serve',help='Start the web service');serve.add_argument('--port',type=int,default=8000)
    args=parser.parse_args()
    if args.command=='serve':
        import uvicorn
        uvicorn.run('aksharacheck.api:app',host='127.0.0.1',port=args.port)
        return
    async def run():
        async def progress(s):print('·',s,flush=True)
        scanner=Scanner(output_dir=args.output,allow_local=args.allow_local,max_pages=args.pages)
        data=await scanner.scan(args.url,args.lang,progress)
        if args.ai:
            data=await explain_and_verify(data,allow_local=args.allow_local,progress=progress)
        write_reports(data,args.output)
        print('Done:',data['summary'],'| reports in',args.output)
        return data
    try:data=asyncio.run(run())
    except Exception as exc:print(f'Error: {exc}',file=sys.stderr);sys.exit(2)
    if args.fail_on=='error' and data['summary']['error']>0:sys.exit(1)
    if args.fail_on=='warning' and (data['summary']['error'] or data['summary']['warning']):sys.exit(1)

if __name__=='__main__':main()
