import { PGlite } from '@electric-sql/pglite'
import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

export async function database(legacy?: string) {
  const db = new PGlite()
  try {
    await db.exec('create role anon; create role authenticated; create role service_role bypassrls;')
    const migrations = fileURLToPath(new URL('../../../supabase/migrations/', import.meta.url))
    for (const file of readdirSync(migrations).filter(file => file.endsWith('.sql')).sort()) {
      if (file.startsWith('20260905200000') && legacy) await db.exec(legacy)
      await db.exec(readFileSync(`${migrations}/${file}`, 'utf8'))
    }
    return db
  } catch (error) { await db.close(); throw error }
}

/** Ephemeral PostgreSQL-only evidence fixtures. Never sent to a live backend. */
export async function publishedFixture(db: PGlite) {
  await db.exec(`
    truncate counties,properties,deals,comps,ingestion_records,ingestion_runs restart identity cascade;
    insert into counties(county_id,county_name,validation_status,extra) values
      ('fixture','Security fixture','valid',jsonb_build_object('authorized_source_fingerprint',repeat('a',64),'ingestion_authorized',true));
    insert into properties(id,apn,county_id,owner_name,lot_size_acres,latitude,longitude,
      source_url,source_record_id,source_fingerprint,source_payload_hash,vacancy_status,has_improvements)
      values(1,'fixture-public','fixture','PRIVATE',1,35,-114,'https://county.example/FeatureServer/0','1',repeat('a',64),repeat('b',64),'qualified',false),
            (2,'fixture-held','fixture','PRIVATE',null,null,null,null,null,null,null,'unknown',null);
    insert into ingestion_runs(id,run_key,county_id,status,finished_at,source_url,metadata) values
      (1,'fixture-run','fixture','completed',now(),'https://county.example/FeatureServer/0',
       jsonb_build_object('source_fingerprint',repeat('a',64),'authorized_source_fingerprint',repeat('a',64),'source_validated_at',now()));
    insert into ingestion_records(id,run_id,county_id,record_key,source_record_id,source_url,raw_payload,
      normalized_payload,field_mapping,property_id,status) values
      (10,1,'fixture','subject','1','https://county.example/FeatureServer/0',
       '{"OBJECTID":1,"APN":"fixture-public","ACRES":1,"PRICE":20000,"COSTS":5000,"OWNER":"PRIVATE"}',
       '{"apn":"fixture-public","lot_size_acres":1,"asking_price":20000,"estimated_costs":5000,"costs_complete":true,"costs_source_url":"https://county.example/costs"}',
       '{"apn":"APN","lot_size_acres":"ACRES","asking_price":"PRICE","estimated_costs":"COSTS"}',1,'candidate');
    insert into deals(id,property_id,status,verification_status,deal_score,asking_price,asking_price_basis,
      estimated_arv_low,estimated_arv_high,estimated_costs,estimated_profit_low,estimated_profit_high,
      recommended_offer_low,recommended_offer_high,source_url,valuation_model,valuation_basis,valuation_confidence,
      financial_evidence,ingestion_record_id) values
      (1,1,'discovered','pending_review',27,20000,'source',80000,100000,5000,55000,75000,12000,16000,
       'https://county.example/FeatureServer/0','vacant_land_comps_v1','comparable_sales',0.75,
       '{"model_version":"vacant_land_comps_v1","asking_price_field":"PRICE","comparable_count":3}',10),
      (2,2,'discovered','source_verified',null,null,null,null,null,null,null,null,null,null,null,null,null,null,'{}',null);
    insert into ingestion_records(id,run_id,county_id,record_key,source_record_id,source_url,raw_payload,normalized_payload,status)
      select 10+i,1,'fixture','comp-'||i,(i+1)::text,'https://county.example/FeatureServer/0',
        jsonb_build_object('OBJECTID',i+1,'APN','comp-'||i,'SALE',80000+10000*i,'SOLD',now()-interval '1 day',
          'ACRES',1,'QUALIFIED',true,'VACANT_AT_SALE',true,'LAT',35+i*0.001,'LON',-114),
        jsonb_build_object('apn','comp-'||i,'last_sale_price',80000+10000*i,'last_sale_date',now()-interval '1 day',
          'lot_size_acres',1,'sale_qualified',true,'vacant_at_sale',true,'latitude',35+i*0.001,'longitude',-114),'held'
        from generate_series(1,3) i;
    insert into comps(deal_id,sale_price,sale_date,distance_miles,lot_size_acres,price_per_acre,source_url,
      source_record_id,source_apn,county_id,sale_qualified,vacant_at_sale,ingestion_record_id)
      select 1,80000+10000*i,now()-interval '1 day',public.distance_miles(35,-114,35+i*0.001,-114),1,80000+10000*i,
        'https://county.example/FeatureServer/0',(i+1)::text,'comp-'||i,'fixture',true,true,10+i from generate_series(1,3) i;
    update deals set verification_status='verified' where id=1;
  `)
}

export async function asRole(db: PGlite, role: 'anon' | 'authenticated' | 'service_role', sql: string) {
  await db.exec(`set role ${role}`)
  try { return await db.query(sql) }
  finally { await db.exec('reset role') }
}
