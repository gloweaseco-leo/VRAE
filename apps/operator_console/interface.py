"""Reusable read interface. Trusted context is passed separately from route input."""
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .contracts import ConsoleError, refuse
from . import views


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes
    content_type: str = 'text/html; charset=utf-8'


class ConsoleInterface:
    def __init__(self, service, *, prefix='/'):
        self.service = service
        self.prefix = prefix

    def dispatch(self, context, method, target):
        try:
            self.service._scope(context)
            if method not in ('GET', 'HEAD'):
                refuse('NOT_IMPLEMENTED')
            if len(target) > 2048 or not target.startswith(self.prefix):
                refuse('UNAUTHORIZED')
            url = urlsplit(target)
            if url.scheme or url.netloc or url.fragment:
                refuse('INVALID_INPUT')
            path = unquote(url.path[len(self.prefix):], errors='strict')
            values = parse_qs(url.query, keep_blank_values=True, strict_parsing=True, max_num_fields=4)
            if any(len(v) != 1 for v in values.values()):
                refuse('INVALID_INPUT')
            q = {k:v[0] for k,v in values.items()}
            if path == 'style.css' and not q:
                return Response(200, Path(__file__).with_name('style.css').read_bytes(),'text/css; charset=utf-8')
            if path == '' and not (set(q)-{'stage','q'}):
                tasks = self.service.pool(context, q.get('stage',''), q.get('q',''))
                body = views.pool(self.prefix,tasks,q.get('stage',''),q.get('q',''))
            else:
                parts = path.split('/')
                if len(parts) < 2 or parts[0] != 'tasks':
                    refuse('NOT_IMPLEMENTED')
                task_id = parts[1]
                if len(parts) == 2 and not q:
                    body = views.detail(self.prefix,self.service.detail(context,task_id))
                elif len(parts) in (3,4) and set(q)=={'version','draft'}:
                    if not q['version'].isascii() or not q['version'].isdigit() or len(q['version'])>4:
                        refuse('INVALID_INPUT')
                    args = (context,task_id,int(q['version']),q['draft'])
                    if len(parts)==3 and parts[2]=='review':
                        body = views.review(self.prefix,*self.service.review(*args))
                    elif len(parts)==4 and parts[2:] == ['evidence','capture']:
                        body = views.capture(self.prefix,*self.service.review(*args))
                    elif len(parts)==4 and parts[2]=='evidence' and parts[3].isascii() and parts[3].isdigit() and len(parts[3])<=2:
                        body = views.evidence(self.prefix,*self.service.evidence(*args,int(parts[3])))
                    else:
                        refuse('NOT_IMPLEMENTED')
                else:
                    refuse('INVALID_INPUT')
            return Response(200,body.encode('utf-8'))
        except ConsoleError as exc:
            code = str(exc)
            status = 403 if code=='UNAUTHORIZED' else 501 if code=='NOT_IMPLEMENTED' else 409 if code in ('STALE_VERSION','SOURCE_INTEGRITY','NOT_READY') else 400
            return Response(status,views.error(self.prefix,code).encode('utf-8'))
        except (ValueError, UnicodeError, TypeError, KeyError):
            return Response(400,views.error(self.prefix,'INVALID_INPUT').encode('utf-8'))
