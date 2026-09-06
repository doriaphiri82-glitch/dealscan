import 'server-only'

export class RequestBodyError extends Error {
  constructor(public readonly status:400|408|413,message:string){super(message)}
}

/** Bounded bytes and elapsed time, including clients that never finish a body. */
export async function readJsonBody(request:Request,maxBytes=2048,timeoutMs=5000):Promise<unknown> {
  if(!Number.isSafeInteger(maxBytes)||maxBytes<1||!Number.isFinite(timeoutMs)||timeoutMs<=0)throw new Error('Invalid request-body limits')
  const declared=request.headers.get('content-length')
  if(declared!==null){
    if(!/^[0-9]+$/.test(declared))throw new RequestBodyError(400,'Invalid request length')
    if(Number(declared)>maxBytes)throw new RequestBodyError(413,'Request too large')
  }
  const stream=request.body
  if(!stream)throw new RequestBodyError(400,'JSON request body required')
  const reader=stream.getReader()
  let rejectStop!:(error:RequestBodyError)=>void
  const stop=new Promise<never>((_,reject)=>{rejectStop=reject})
  const cancel=(error:RequestBodyError)=>{
    rejectStop(error)
    // A peer's cancellation callback must not hold the response open either.
    void reader.cancel().catch(()=>{})
  }
  const abort=()=>cancel(new RequestBodyError(400,'Request was canceled'))
  const timer=setTimeout(()=>cancel(new RequestBodyError(408,'Request body timed out')),timeoutMs)
  if(request.signal.aborted)abort()
  else request.signal.addEventListener('abort',abort,{once:true})
  async function read(){
    const chunks:Uint8Array[]=[]
    let length=0
    for(;;){
      const {done,value}=await reader.read()
      if(done)break
      if(!(value instanceof Uint8Array))throw new RequestBodyError(400,'Invalid request body')
      length+=value.byteLength
      if(length>maxBytes)throw new RequestBodyError(413,'Request too large')
      chunks.push(new Uint8Array(value))
    }
    const body=new Uint8Array(length)
    let offset=0
    for(const chunk of chunks){body.set(chunk,offset);offset+=chunk.byteLength}
    // Malformed UTF-8 must not silently change the submitted identity.
    return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(body)) as unknown
  }
  try {
    return await Promise.race([stop,read()])
  } catch(error){
    void reader.cancel().catch(()=>{})
    if(error instanceof RequestBodyError)throw error
    throw new RequestBodyError(400,'Invalid JSON or UTF-8 request')
  } finally {
    clearTimeout(timer)
    request.signal.removeEventListener('abort',abort)
    reader.releaseLock()
  }
}
