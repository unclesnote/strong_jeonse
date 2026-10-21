import {env} from 'cloudflare:workers';
import config from '../../../competition-config.json';
import {CompetitionService,sqlStore,api} from '../../../../competition.mjs';
let service: CompetitionService|null=null;
export async function handle(request:Request){
 if(!env.DB)return Response.json({error:'신청 현황 저장소가 연결되지 않았습니다.'},{status:503});
 if(!service)service=new CompetitionService({meta:config,store:sqlStore(env.DB)});
 return api(request,service);
}
