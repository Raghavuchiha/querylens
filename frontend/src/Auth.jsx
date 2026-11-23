import { useState } from 'react';
import { ArrowRight, LockKeyhole, Mail, Sparkles } from 'lucide-react';
import { supabase } from './supabase';

export default function Auth() {
  const [signup, setSignup] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  async function submit(event) {
    event.preventDefault();
    if (!supabase || busy) return;
    setBusy(true);
    setNotice('');
    setError('');
    try {
      if (signup) {
        const { data, error } = await supabase.auth.signUp({
          email: email.trim(),
          password,
          options: { emailRedirectTo: window.location.origin },
        });
        if (error) throw error;
        if (!data.session) setNotice('Check your email to confirm your account, then sign in.');
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
        if (error) throw error;
      }
    } catch (err) {
      setError(err.message || 'Could not sign in.');
    } finally {
      setBusy(false);
    }
  }

  if (!supabase) return (
    <div className="auth-page"><div className="auth-card">
      <div className="auth-brand">query<span>lens</span> ✳</div>
      <h1>SETUP<br/><span>NEEDED.</span></h1>
      <p>Add VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY to frontend/.env and restart Vite.</p>
    </div></div>
  );

  return <div className="auth-page"><div className="auth-card">
    <div className="auth-brand">query<span>lens</span> ✳</div>
    <div className="auth-kicker"><Sparkles size={15}/> YOUR DOCUMENTS. YOUR WORKSPACE.</div>
    <h1>{signup ? 'JOIN THE' : 'WELCOME'}<br/><span>{signup ? 'CURIOUS.' : 'BACK.'}</span></h1>
    <p>{signup ? 'Create an account to build your own knowledge base.' : 'Sign in to your private document workspace.'}</p>
    <form onSubmit={submit} className="auth-form">
      <label htmlFor="email"><Mail size={15}/> EMAIL ADDRESS</label>
      <input id="email" type="email" required autoComplete="email" placeholder="you@example.com" value={email} onChange={e=>setEmail(e.target.value)}/>
      <label htmlFor="password"><LockKeyhole size={15}/> PASSWORD</label>
      <input id="password" type="password" minLength={6} required autoComplete={signup?'new-password':'current-password'} placeholder="At least 6 characters" value={password} onChange={e=>setPassword(e.target.value)}/>
      {error && <div className="auth-error" role="alert">{error}</div>}
      {notice && <div className="auth-notice" role="status">{notice}</div>}
      <button className="auth-submit" type="submit" disabled={busy}>{busy ? 'PLEASE WAIT…' : signup ? 'CREATE ACCOUNT' : 'SIGN IN'} <ArrowRight size={18}/></button>
    </form>
    <button className="auth-switch" onClick={()=>{setSignup(!signup);setError('');setNotice('');}}>{signup ? 'Already have an account? Sign in' : 'New to QueryLens? Create an account'}</button>
    <div className="auth-bottom">RESEARCH, MINUS THE NOISE. ↗</div>
  </div></div>;
}
