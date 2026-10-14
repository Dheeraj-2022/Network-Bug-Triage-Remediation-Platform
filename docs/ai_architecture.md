# AI Multi-Agent Architecture

This document describes the AI reasoning layer added on top of the existing
deterministic triage/remediation stack. The legacy pipeline (rules engine,
XGBoost classifier, NLP embeddings, Ansible remediation, Kafka transport,
dashboard) is **unchanged**; the AI layer augments it.

## Design goals

1. **Never break existing functionality.** The AI layer is optional and imported
   lazily. If it fails to initialise, the legacy path continues untouched.
2. **Graceful degradation.** Every optional dependency (Vertex AI, LangChain,
   LangGraph, ADK, Chroma, Prometheus) is imported defensively. With none of
   them installed, the platform runs a deterministic offline reasoner and a
   numpy cosine-similarity retriever.
3. **Reuse, don't replace.** XGBoost stays the fast first-pass classifier and the
   existing sentence-transformer embeddings are reused for retrieval. The LLM
   only performs the deeper reasoning steps.

## Data flow

```drawio
<mxfile>
  <diagram id="Wbl7sNKW2hGcD68ESCdW" name="Page-1">
    <mxGraphModel dx="1328" dy="1632" grid="1" gridSize="10" guides="1" tooltips="0" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="850" pageHeight="1100" math="0" shadow="0">
      <root>
        <mxCell id="XwwPOGP83xqGBCw4e9Zp-0" />
        <mxCell id="XwwPOGP83xqGBCw4e9Zp-1" parent="XwwPOGP83xqGBCw4e9Zp-0" />
        <UserObject label="" mermaidData="{&#xa;  &quot;data&quot;: &quot;flowchart TD\r\n    A[Telemetry Agent] --&gt; K[Kafka telemetry.events]\r\n    K --&gt; P[Processor]\r\n    P --&gt; R[Rules Engine]\r\n    P --&gt; M[XGBoost Classifier]\r\n    P --&gt; N[NLP Log Parser]\r\n    P --&gt; O[AI Orchestrator]\r\n    O --&gt; PL[Planner Agent]\r\n    PL --&gt; TA[Telemetry Analysis Agent]\r\n    TA --&gt; RET[Retriever Agent]\r\n    RET --&gt; VDB[(Vector DB)]\r\n    RET --&gt; KB[(Knowledge Base)]\r\n    RET --&gt; MEM[(Memory: incidents/host/patterns)]\r\n    RET --&gt; RCA[Root Cause Analysis Agent]\r\n    RCA --&gt; LLM[Vertex AI Gemini / Heuristic fallback]\r\n    RCA --&gt; REM[Remediation Agent]\r\n    REM --&gt; HA{Human Approval}\r\n    HA --&gt;|approved| ANS[Ansible Execution]\r\n    ANS --&gt; VAL[Validation Agent]\r\n    HA --&gt;|pending| DASH[Dashboard]\r\n    VAL --&gt; AUD[Audit Agent]\r\n    AUD --&gt; MEM\r\n    AUD --&gt; DASH&quot;,&#xa;  &quot;config&quot;: null&#xa;}" id="PPguYXXUbtKRSqFXcxLR-0">
          <mxCell connectable="0" parent="XwwPOGP83xqGBCw4e9Zp-1" style="group;transparentBounds=1;editIcon=1;lockedGroup=0;groupPadding=10;" vertex="1">
            <mxGeometry as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Telemetry Agent" mermaidId="n:A" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Telemetry Agent" id="XwwPOGP83xqGBCw4e9Zp-2">
          <mxCell parent="PPguYXXUbtKRSqFXcxLR-0" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="177" x="126" y="10" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Kafka telemetry.events" mermaidId="n:K" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Kafka telemetry.events" id="XwwPOGP83xqGBCw4e9Zp-3">
          <mxCell parent="PPguYXXUbtKRSqFXcxLR-0" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="227" x="101" y="114" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Processor" mermaidId="n:P" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Processor" id="XwwPOGP83xqGBCw4e9Zp-4">
          <mxCell parent="PPguYXXUbtKRSqFXcxLR-0" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="127" x="151" y="218" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Rules Engine" mermaidId="n:R" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Rules Engine" id="XwwPOGP83xqGBCw4e9Zp-5">
          <mxCell parent="PPguYXXUbtKRSqFXcxLR-0" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="150" x="10" y="322" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="XGBoost Classifier" mermaidId="n:M" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="XGBoost Classifier" id="XwwPOGP83xqGBCw4e9Zp-6">
          <mxCell parent="PPguYXXUbtKRSqFXcxLR-0" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="189" x="210" y="322" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="NLP Log Parser" mermaidId="n:N" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="NLP Log Parser" id="XwwPOGP83xqGBCw4e9Zp-7">
          <mxCell parent="PPguYXXUbtKRSqFXcxLR-0" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="166" x="449" y="322" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="AI Orchestrator" mermaidId="n:O" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="AI Orchestrator" id="XwwPOGP83xqGBCw4e9Zp-8">
          <mxCell parent="PPguYXXUbtKRSqFXcxLR-0" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="170" x="665" y="322" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Planner Agent" mermaidId="n:PL" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Planner Agent" id="XwwPOGP83xqGBCw4e9Zp-9">
          <mxCell parent="PPguYXXUbtKRSqFXcxLR-0" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="160" x="670" y="426" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Telemetry Analysis Agent" mermaidId="n:TA" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Telemetry Analysis Agent" id="XwwPOGP83xqGBCw4e9Zp-10">
          <mxCell parent="PPguYXXUbtKRSqFXcxLR-0" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="238" x="631" y="530" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Retriever Agent" mermaidId="n:RET" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Retriever Agent" id="XwwPOGP83xqGBCw4e9Zp-11">
          <mxCell parent="PPguYXXUbtKRSqFXcxLR-0" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="171" x="665" y="634" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Vector DB" mermaidId="n:VDB" mermaidBaseStyle="html=1;shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=10;strokeWidth=1;whiteSpace=wrap;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Vector DB" id="XwwPOGP83xqGBCw4e9Zp-12">
          <mxCell parent="PPguYXXUbtKRSqFXcxLR-0" style="html=1;shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=10;strokeWidth=1;whiteSpace=wrap;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="67" width="85" x="296" y="738" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Knowledge Base" mermaidId="n:KB" mermaidBaseStyle="html=1;shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=10;strokeWidth=1;whiteSpace=wrap;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Knowledge Base" id="XwwPOGP83xqGBCw4e9Zp-13">
          <mxCell parent="PPguYXXUbtKRSqFXcxLR-0" style="html=1;shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=10;strokeWidth=1;whiteSpace=wrap;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="67" width="130" x="431" y="738" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Memory: incidents/host/patterns" mermaidId="n:MEM" mermaidBaseStyle="html=1;shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=10;strokeWidth=1;whiteSpace=wrap;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Memory: incidents/host/patterns" id="XwwPOGP83xqGBCw4e9Zp-14">
          <mxCell parent="PPguYXXUbtKRSqFXcxLR-0" style="html=1;shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=10;strokeWidth=1;whiteSpace=wrap;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="67" width="254" x="479" y="1543" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Root Cause Analysis Agent" mermaidId="n:RCA" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Root Cause Analysis Agent" id="XwwPOGP83xqGBCw4e9Zp-15">
          <mxCell parent="PPguYXXUbtKRSqFXcxLR-0" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="245" x="826" y="745" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Vertex AI Gemini / Heuristic fallback" mermaidId="n:LLM" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Vertex AI Gemini / Heuristic fallback" id="XwwPOGP83xqGBCw4e9Zp-16">
          <mxCell parent="PPguYXXUbtKRSqFXcxLR-0" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="324" x="631" y="855" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Remediation Agent" mermaidId="n:REM" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Remediation Agent" id="XwwPOGP83xqGBCw4e9Zp-17">
          <mxCell parent="PPguYXXUbtKRSqFXcxLR-0" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="195" x="1005" y="855" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Human Approval" mermaidId="n:HA" mermaidBaseStyle="rhombus;html=1;strokeWidth=1;whiteSpace=wrap;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Human Approval" id="XwwPOGP83xqGBCw4e9Zp-18">
          <mxCell parent="PPguYXXUbtKRSqFXcxLR-0" style="rhombus;html=1;strokeWidth=1;whiteSpace=wrap;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="203" width="203" x="1001" y="959" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Ansible Execution" mermaidId="n:ANS" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Ansible Execution" id="XwwPOGP83xqGBCw4e9Zp-19">
          <mxCell parent="PPguYXXUbtKRSqFXcxLR-0" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="187" x="820" y="1231" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Validation Agent" mermaidId="n:VAL" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Validation Agent" id="XwwPOGP83xqGBCw4e9Zp-20">
          <mxCell parent="PPguYXXUbtKRSqFXcxLR-0" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="177" x="825" y="1335" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Dashboard" mermaidId="n:DASH" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Dashboard" id="XwwPOGP83xqGBCw4e9Zp-21">
          <mxCell parent="PPguYXXUbtKRSqFXcxLR-0" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="134" x="1102" y="1550" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Audit Agent" mermaidId="n:AUD" mermaidBaseStyle="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Audit Agent" id="XwwPOGP83xqGBCw4e9Zp-22">
          <mxCell parent="PPguYXXUbtKRSqFXcxLR-0" style="html=1;whiteSpace=wrap;strokeWidth=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="54" width="143" x="842" y="1439" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:A-&gt;K#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.5;exitY=1;entryX=0.5;entryY=0;" mermaidBaseValue="" id="XwwPOGP83xqGBCw4e9Zp-23">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-2" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.5;exitY=1;entryX=0.5;entryY=0;" target="XwwPOGP83xqGBCw4e9Zp-3">
            <mxGeometry relative="1" as="geometry">
              <Array as="points" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:K-&gt;P#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.5;exitY=1;entryX=0.5;entryY=0;" mermaidBaseValue="" id="XwwPOGP83xqGBCw4e9Zp-24">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-3" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.5;exitY=1;entryX=0.5;entryY=0;" target="XwwPOGP83xqGBCw4e9Zp-4">
            <mxGeometry relative="1" as="geometry">
              <Array as="points" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:P-&gt;R#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0;exitY=0.96;entryX=0.5;entryY=0;" mermaidBaseValue="" id="XwwPOGP83xqGBCw4e9Zp-25">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-4" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0;exitY=0.96;entryX=0.5;entryY=0;" target="XwwPOGP83xqGBCw4e9Zp-5">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="85" y="297" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:P-&gt;M#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.87;exitY=1;entryX=0.5;entryY=0;" mermaidBaseValue="" id="XwwPOGP83xqGBCw4e9Zp-26">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-4" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.87;exitY=1;entryX=0.5;entryY=0;" target="XwwPOGP83xqGBCw4e9Zp-6">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="305" y="297" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:P-&gt;N#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.69;entryX=0.5;entryY=0;" mermaidBaseValue="" id="XwwPOGP83xqGBCw4e9Zp-27">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-4" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.69;entryX=0.5;entryY=0;" target="XwwPOGP83xqGBCw4e9Zp-7">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="532" y="297" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:P-&gt;O#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.61;entryX=0.5;entryY=0;" mermaidBaseValue="" id="XwwPOGP83xqGBCw4e9Zp-28">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-4" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.61;entryX=0.5;entryY=0;" target="XwwPOGP83xqGBCw4e9Zp-8">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="750" y="297" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:O-&gt;PL#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.5;exitY=1;entryX=0.5;entryY=0;" mermaidBaseValue="" id="XwwPOGP83xqGBCw4e9Zp-29">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-8" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.5;exitY=1;entryX=0.5;entryY=0;" target="XwwPOGP83xqGBCw4e9Zp-9">
            <mxGeometry relative="1" as="geometry">
              <Array as="points" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:PL-&gt;TA#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.5;exitY=1;entryX=0.5;entryY=0;" mermaidBaseValue="" id="XwwPOGP83xqGBCw4e9Zp-30">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-9" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.5;exitY=1;entryX=0.5;entryY=0;" target="XwwPOGP83xqGBCw4e9Zp-10">
            <mxGeometry relative="1" as="geometry">
              <Array as="points" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:TA-&gt;RET#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.5;exitY=1;entryX=0.5;entryY=0;" mermaidBaseValue="" id="XwwPOGP83xqGBCw4e9Zp-31">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-10" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.5;exitY=1;entryX=0.5;entryY=0;" target="XwwPOGP83xqGBCw4e9Zp-11">
            <mxGeometry relative="1" as="geometry">
              <Array as="points" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:RET-&gt;VDB#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0;exitY=0.7;entryX=0.51;entryY=0;" mermaidBaseValue="" id="XwwPOGP83xqGBCw4e9Zp-32">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-11" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0;exitY=0.7;entryX=0.51;entryY=0;" target="XwwPOGP83xqGBCw4e9Zp-12">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="339" y="713" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:RET-&gt;KB#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0;exitY=0.83;entryX=0.5;entryY=0;" mermaidBaseValue="" id="XwwPOGP83xqGBCw4e9Zp-33">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-11" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0;exitY=0.83;entryX=0.5;entryY=0;" target="XwwPOGP83xqGBCw4e9Zp-13">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="496" y="713" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:RET-&gt;MEM#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.03;exitY=1;entryX=0.48;entryY=0;" mermaidBaseValue="" id="XwwPOGP83xqGBCw4e9Zp-34">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-11" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.03;exitY=1;entryX=0.48;entryY=0;" target="XwwPOGP83xqGBCw4e9Zp-14">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="596" y="713" />
                <mxPoint x="596" y="772" />
                <mxPoint x="596" y="830" />
                <mxPoint x="596" y="882" />
                <mxPoint x="596" y="934" />
                <mxPoint x="596" y="1061" />
                <mxPoint x="596" y="1197" />
                <mxPoint x="596" y="1258" />
                <mxPoint x="596" y="1310" />
                <mxPoint x="596" y="1362" />
                <mxPoint x="596" y="1414" />
                <mxPoint x="596" y="1466" />
                <mxPoint x="596" y="1518" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:RET-&gt;RCA#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.91;entryX=0.5;entryY=0;" mermaidBaseValue="" id="XwwPOGP83xqGBCw4e9Zp-35">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-11" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=1;exitY=0.91;entryX=0.5;entryY=0;" target="XwwPOGP83xqGBCw4e9Zp-15">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="948" y="713" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:RCA-&gt;LLM#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.21;exitY=1;entryX=0.5;entryY=0;" mermaidBaseValue="" id="XwwPOGP83xqGBCw4e9Zp-36">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-15" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.21;exitY=1;entryX=0.5;entryY=0;" target="XwwPOGP83xqGBCw4e9Zp-16">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="793" y="830" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:RCA-&gt;REM#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.79;exitY=1;entryX=0.5;entryY=0;" mermaidBaseValue="" id="XwwPOGP83xqGBCw4e9Zp-37">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-15" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.79;exitY=1;entryX=0.5;entryY=0;" target="XwwPOGP83xqGBCw4e9Zp-17">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="1103" y="830" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:REM-&gt;HA#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.5;exitY=1;entryX=0.5;entryY=0;" mermaidBaseValue="" id="XwwPOGP83xqGBCw4e9Zp-38">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-17" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.5;exitY=1;entryX=0.5;entryY=0;" target="XwwPOGP83xqGBCw4e9Zp-18">
            <mxGeometry relative="1" as="geometry">
              <Array as="points" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="approved" mermaidId="e:HA-&gt;ANS#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);html=1;fontSize=16;labelBackgroundColor=light-dark(#E8E8E88D,#2a2a2a8D);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontColor=light-dark(#333333,#cccccc);exitX=0;exitY=0.86;entryX=0.5;entryY=0;" mermaidBaseValue="approved" id="XwwPOGP83xqGBCw4e9Zp-39">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-18" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);html=1;fontSize=16;labelBackgroundColor=light-dark(#E8E8E88D,#2a2a2a8D);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontColor=light-dark(#333333,#cccccc);exitX=0;exitY=0.86;entryX=0.5;entryY=0;" target="XwwPOGP83xqGBCw4e9Zp-19">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="914" y="1197" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:ANS-&gt;VAL#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.5;exitY=1;entryX=0.5;entryY=0;" mermaidBaseValue="" id="XwwPOGP83xqGBCw4e9Zp-40">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-19" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.5;exitY=1;entryX=0.5;entryY=0;" target="XwwPOGP83xqGBCw4e9Zp-20">
            <mxGeometry relative="1" as="geometry">
              <Array as="points" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="pending" mermaidId="e:HA-&gt;DASH#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);html=1;fontSize=16;labelBackgroundColor=light-dark(#E8E8E88D,#2a2a2a8D);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontColor=light-dark(#333333,#cccccc);exitX=0.78;exitY=1;entryX=0.53;entryY=0;" mermaidBaseValue="pending" id="XwwPOGP83xqGBCw4e9Zp-41">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-18" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);html=1;fontSize=16;labelBackgroundColor=light-dark(#E8E8E88D,#2a2a2a8D);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontColor=light-dark(#333333,#cccccc);exitX=0.78;exitY=1;entryX=0.53;entryY=0;" target="XwwPOGP83xqGBCw4e9Zp-21">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="1179" y="1197" />
                <mxPoint x="1179" y="1258" />
                <mxPoint x="1179" y="1310" />
                <mxPoint x="1179" y="1362" />
                <mxPoint x="1179" y="1414" />
                <mxPoint x="1179" y="1466" />
                <mxPoint x="1179" y="1518" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:VAL-&gt;AUD#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.5;exitY=1;entryX=0.5;entryY=0;" mermaidBaseValue="" id="XwwPOGP83xqGBCw4e9Zp-42">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-20" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.5;exitY=1;entryX=0.5;entryY=0;" target="XwwPOGP83xqGBCw4e9Zp-22">
            <mxGeometry relative="1" as="geometry">
              <Array as="points" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:AUD-&gt;MEM#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.31;exitY=1;entryX=1;entryY=0.06;" mermaidBaseValue="" id="XwwPOGP83xqGBCw4e9Zp-43">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-22" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.31;exitY=1;entryX=1;entryY=0.06;" target="XwwPOGP83xqGBCw4e9Zp-14">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="860" y="1518" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:AUD-&gt;DASH#0" mermaidBaseStyle="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.74;exitY=1;entryX=0;entryY=0.11;" mermaidBaseValue="" id="XwwPOGP83xqGBCw4e9Zp-44">
          <mxCell edge="1" parent="PPguYXXUbtKRSqFXcxLR-0" source="XwwPOGP83xqGBCw4e9Zp-22" style="curved=1;startArrow=none;endArrow=block;endSize=7;strokeColor=light-dark(#333333,#cccccc);exitX=0.74;exitY=1;entryX=0;entryY=0.11;" target="XwwPOGP83xqGBCw4e9Zp-21">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="980" y="1518" />
              </Array>
            </mxGeometry>
          </mxCell>
        </UserObject>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>

```

## Module map (`controller/ai/`)

| Module | Purpose |
|--------|---------|
| `config.py` | AI configuration (file + env), Vertex/retrieval/memory settings |
| `prompts.py` | Versioned prompt library (RCA, remediation, validation) |
| `llm.py` | LLM facade: Vertex Gemini backend + deterministic heuristic backend |
| `vector_store.py` | Pluggable vector store (Chroma → numpy cosine fallback) |
| `knowledge_base.py` | Loads runbooks / RDMA / kernel docs into chunks |
| `retriever.py` | Hybrid retrieval (vector + keyword + incident history) |
| `memory.py` | Conversation/incident/host/remediation/pattern memory |
| `agents.py` | The eight agents operating over a shared `WorkflowState` |
| `orchestrator.py` | ADK/LangGraph-style graph executor + human-approval gate |
| `evaluation.py` | Reproducible accuracy harness |
| `monitoring.py` | Counters + latency (Prometheus optional) |

## Human-approval gate

When `require_human_approval` is set (default), the Remediation Agent emits a
plan with `status = pending_approval` and the orchestrator **pauses before
execution**. The Flask endpoint `POST /api/ai/approve` resumes the workflow
(validation + audit) once a human approves. Kernel panics and unknown domains
are never auto-remediated regardless of confidence.

## Enabling Vertex AI Gemini

```bash
export GOOGLE_CLOUD_PROJECT=my-project
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json
export NBT_VERTEX_MODEL=gemini-1.5-pro
pip install google-cloud-aiplatform
```

With these set, `GET /api/ai/status` reports `"llm_backend": "vertex-gemini"`
and all reasoning is performed through Vertex AI. Without them it reports
`"heuristic"` and the platform remains fully functional offline.
