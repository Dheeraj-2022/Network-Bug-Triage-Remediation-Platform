import { useState } from 'react';

const APPROVER_RE = /^[A-Za-z0-9][A-Za-z0-9 ._@-]{0,63}$/;
const APPROVER_KEY = 'nbt_approver';

/** Approver names are self-asserted unless an authenticating proxy is in front of the API. */
export function useApprover(): [string, (v: string) => void, boolean] {
  const [name, setName] = useState(() => sessionStorage.getItem(APPROVER_KEY) || '');
  const update = (v: string) => {
    setName(v);
    sessionStorage.setItem(APPROVER_KEY, v);
  };
  return [name, update, APPROVER_RE.test(name)];
}
