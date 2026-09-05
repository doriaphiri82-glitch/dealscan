'use client'
import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchDealByApn, type Deal } from './deals'
import { parcelKey, type ParcelRef } from './parcels'

interface ParcelState { key:string; deal:Deal|null; loading:boolean; error:string }

/** An older response can never replace another county/parcel or a newer retry. */
export function useParcel({apn,county_id}:ParcelRef, refreshMs=60000) {
  const key=parcelKey({apn,county_id})
  const [state,setState]=useState<ParcelState>({key,deal:null,loading:true,error:''})
  const sequence=useRef(0)
  const request=useRef<AbortController|null>(null)
  const load=useCallback(async(silent=false)=>{
    const version=++sequence.current
    request.current?.abort()
    const controller=new AbortController()
    request.current=controller
    setState(previous=>({key,deal:silent&&previous.key===key?previous.deal:null,loading:!silent,error:''}))
    const current=()=>sequence.current===version&&!controller.signal.aborted
    try {
      const response=await fetchDealByApn(apn,county_id,{signal:controller.signal})
      if(current())setState({key,deal:response?.deal??null,loading:false,error:''})
    } catch(error) {
      if(current())setState({key,deal:null,loading:false,error:error instanceof Error?error.message:'This parcel could not be checked.'})
    }
  },[key,apn,county_id])

  useEffect(()=>{
    void load()
    const timer=refreshMs>0?setInterval(()=>void load(true),refreshMs):null
    return()=>{
      if(timer!==null)clearInterval(timer)
      sequence.current++
      request.current?.abort()
    }
  },[load,refreshMs])

  useEffect(()=>{
    if(!state.deal)return
    const expired=state.deal
    const timer=setTimeout(()=>setState(current=>current.key===state.key&&current.deal===expired
      ? {...current,deal:null,loading:false,error:'This verification has expired. Refresh to check for a new review.'}:current),
      Math.max(0,Date.parse(expired.verification_expires_at)-Date.now()+1))
    return()=>clearTimeout(timer)
  },[state.deal,state.key])

  // Effects run after rendering. Do not show the previous parcel for even that
  // intermediate render when an identical APN is selected in a different county.
  const visible=state.key===key?state:{key,deal:null,loading:true,error:''}
  return {...visible,load}
}
