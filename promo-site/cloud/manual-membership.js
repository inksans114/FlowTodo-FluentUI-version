// Personal QR receipts are checked by the administrator, never auto-trusted.
export async function manualMembership({path,method,body,session,q,now,json,env,fail}) {
  if(path==='/api/payments/manual/orders'){
    if(method==='GET'){const rows=await q('SELECT * FROM manual_orders WHERE user_id=? ORDER BY created_at DESC LIMIT 20',session.id).all();return json({orders:rows.results});}
    if(method==='POST'){
      if(!env.MANUAL_PAYMENTS_ENABLED)fail(503,'人工收款暂未开放。');
      if(!['lite','standard'].includes(body.plan)||body.cycle!=='monthly')fail(400,'赞赏码目前只支持两档月付会员。');
      const prior=await q("SELECT * FROM manual_orders WHERE user_id=? AND status IN ('awaiting_payment','awaiting_review') ORDER BY created_at DESC LIMIT 1",session.id).first();
      if(prior){if(prior.plan!==body.plan)fail(409,'已有待处理订单，请先完成或联系管理员。');return json({order:prior});}
      const order={id:crypto.randomUUID(),user_id:session.id,plan:body.plan,amount_cents:body.plan==='lite'?599:999,status:'awaiting_payment',receipt:'',created_at:now,updated_at:now,account_name:session.name};
      try{await q('INSERT INTO manual_orders VALUES(?,?,?,?,?,?,?,?,?)',...Object.values(order)).run();}catch{fail(409,'已有待处理订单，请刷新后查看。');}return json({order},201);
    }
  }
  if(path==='/api/payments/manual/cancel'&&method==='POST'){
    const changed=await q("UPDATE manual_orders SET status='rejected',updated_at=? WHERE id=? AND user_id=? AND status='awaiting_payment'",now,String(body.orderId||''),session.id).run();if(!changed.meta.changes)fail(409,'已提交付款信息的订单需要联系管理员处理。');return json({message:'未付款订单已取消。'});
  }
  if(path==='/api/admin/manual/reject'&&method==='POST'){
    if(session.role!=='admin')fail(403,'需要管理员权限。');
    const changed=await q("UPDATE manual_orders SET status='rejected',updated_at=? WHERE id=? AND status IN ('awaiting_payment','awaiting_review')",now,String(body.orderId||'')).run();if(!changed.meta.changes)fail(409,'订单已经处理。');return json({message:'订单标记为未通过；此操作不会退款。'});
  }
  if(path==='/api/payments/manual/receipt'&&method==='POST'){
    const receipt=String(body.receipt||'').trim(),accountName=String(body.accountName||'').trim();if(receipt.length<6||receipt.length>100||accountName.length<1||accountName.length>40)fail(400,'请填写账户昵称（1–40 字）与付款单号（6–100 个字符）。');
    const changed=await q("UPDATE manual_orders SET receipt=?,account_name=?,status='awaiting_review',updated_at=? WHERE id=? AND user_id=? AND status IN ('awaiting_payment','awaiting_review')",receipt,accountName,now,String(body.orderId||''),session.id).run();
    if(!changed.meta.changes)fail(404,'订单不存在或已经处理。');return json({message:'付款信息已提交，正在等待管理员核实到账。'});
  }
  if(path==='/api/admin/manual/orders'&&method==='GET'){
    if(session.role!=='admin')fail(403,'需要管理员权限。');
    const rows=await q('SELECT o.*,u.email,u.name FROM manual_orders o JOIN users u ON u.id=o.user_id ORDER BY o.created_at DESC LIMIT 100').all();return json({orders:rows.results});
  }
  if(path!=='/api/admin/membership'||method!=='POST')return null;
  if(session.role!=='admin')fail(403,'需要管理员权限。');
  let email=String(body.email||'').trim().toLowerCase();const receipt=String(body.receipt||'').trim();let order=null;
  if(body.orderId){order=await q("SELECT o.*,u.email FROM manual_orders o JOIN users u ON u.id=o.user_id WHERE o.id=?",String(body.orderId)).first();if(!order)fail(404,'订单不存在。');if(order.plan!==body.plan||body.days!==30)fail(400,'请按订单原套餐开通 30 天。');if(order.status==='approved')return json({message:'订单已经开通，没有重复操作。'});if(order.status!=='awaiting_review')fail(409,'请等待用户提交付款信息后再确认。');email=order.email;}
  if(!['free','lite','standard'].includes(body.plan)||!Number.isInteger(body.days)||body.days<1||body.days>366||receipt.length<6||receipt.length>100||body.confirmed!==true)fail(400,'请选择方案、1–366 天，并填写已核实的收款单号或操作备注。');
  const target=await q('SELECT id,plan FROM users WHERE email=?',email).first();
  if(!target)fail(404,'该邮箱尚未注册。');
  const prior=await q('SELECT * FROM membership_audit WHERE receipt=?',receipt).first();
  if(prior){if(prior.user_id===target.id&&prior.new_plan===body.plan&&prior.days===body.days)return json({message:'这笔操作已完成，没有重复延长。'});fail(409,'该收款单号已经用于另一笔操作。');}
  const active=order?await q('SELECT plan,expires FROM manual_memberships WHERE user_id=?',target.id).first():null;
  const starts=active?.plan===body.plan?Math.max(now,active.expires):now;
  const expires=body.plan==='free'?now:starts+body.days*86400000;
  try{
    await env.DB.batch([
      q('INSERT INTO membership_audit VALUES(?,?,?,?,?,?,?,?)',order?.id||crypto.randomUUID(),session.id,target.id,target.plan,body.plan,body.days,receipt,now),
      q('INSERT INTO manual_memberships VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET plan=excluded.plan,expires=excluded.expires,updated_at=excluded.updated_at',target.id,body.plan,expires,now),
      q('UPDATE users SET plan=? WHERE id=?',body.plan,target.id),
      ...(order?[q("UPDATE manual_orders SET status='approved',updated_at=? WHERE id=?",now,order.id)]:[]),
    ]);
  }catch{fail(409,'操作未完成，请刷新并核查收款单号。');}
  return json({message:env.AI_DIRECT_ENABLED?'会员类型和云端额度已更新，软件官方 AI 按本期套餐自动获得额度。':'会员类型和云端额度已更新。官方 AI 需单独确认开通。',expires});
}
export async function expireManualMembership(q,session,now){
  const membership=await q('SELECT plan,expires FROM manual_memberships WHERE user_id=?',session.id).first();
  if(membership&&membership.expires<=now&&session.plan===membership.plan){
    await q('UPDATE users SET plan=? WHERE id=? AND plan=?','free',session.id,membership.plan).run();session.plan='free';
  }
}
