# Data Lineage Support on Fabric Warehouse

## Problem Statement

As Fabric Warehouse becomes a core analytical engine for enterprise and regulated workloads, customers increasingly rely on complex SQL transformations implemented through stored procedures, dynamic SQL, and hybrid pipelines. Today, these transformations operate as an operational black box. While Fabric and Purview provide artifact-level lineage, they do not expose how Warehouse tables and columns are actually produced at runtime. This gap limits customers’ ability to troubleshoot failures, safely evolve schemas, perform reliable impact analysis, and satisfy governance and audit requirements.

Leadership feedback and customer escalations have consistently highlighted that without runtime, granular lineage, Fabric Warehouse cannot meet enterprise expectations for trust, observability, and governance. Static definitions alone are no longer sufficient; customers need lineage that reflects what actually executed and affected data.

## Value Proposition

Fabric Warehouse Granular Lineage introduces automated, runtime-derived lineage at table and column level, captured directly from the SQL engine using an event-based provenance architecture. By decoupling lineage capture from query execution, the system provides deep visibility into stored procedures, dynamic SQL, and data movement without introducing performance overhead or reliability risk.

Lineage signals are standardized, system-managed, and integrated natively into Fabric Lineage and Microsoft Purview, ensuring consistency across the Fabric ecosystem. This enables engineers to reason about real data flows, while governance teams consume the same trusted signals for compliance and enterprise data mapping, without requiring direct access to Warehouse internals.

## Why This Is Important

Granular lineage is a foundational trust capability, not a convenience feature. It directly addresses top leadership priorities around enterprise readiness, governance credibility, and cross-item intelligence across Fabric. Without it, Warehouse remains disconnected from the broader Fabric data estate, weakening the end-to-end lineage story and limiting adoption in regulated environments.

This capability also establishes the technical foundation for future investments, including AI-assisted impact analysis, lineage-driven Copilot experiences, and advanced governance automation. In short, it turns lineage from static documentation into an operational signal that the platform can reason over.

## Conclusion

Fabric Warehouse Granular Lineage closes a critical platform gap by making data transformations observable, governable, and trustworthy at runtime. It aligns directly with leadership expectations for Fabric as an enterprise-grade data platform and provides a durable foundation for future innovation. Treating this work as a planning priority ensures Fabric Warehouse scales with confidence, not complexity.