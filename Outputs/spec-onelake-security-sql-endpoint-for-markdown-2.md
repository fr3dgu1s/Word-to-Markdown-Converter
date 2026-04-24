| OneLake Security for SQL Endpoint   | OneLake Security for SQL Endpoint                                          | OneLake Security for SQL Endpoint   | OneLake Security for SQL Endpoint   | OneLake Security for SQL Endpoint     |
|-------------------------------------|----------------------------------------------------------------------------|-------------------------------------|-------------------------------------|---------------------------------------|
| Program Manager:                    | Freddie Santos                                                             |                                     | VSTS ID:                            |                                       |
| Engineering Manager:                | Don Reamey,                                                                |                                     | Status:                             | Draft &#124; For Review&#124; Signoff |
| Engineer:                           | Abhishek Jain, Anthony Toribo, Sree Gouri Varshini Kodem, Nneoma Oradiegwu |                                     | Last Modified:                      | 08/07/2025                            |
| UX Designer:                        | Ke Hu                                                                      |                                     | Release/Milestone:                  | PrPr &#124; PuPr &#124; GA            |
| Architects:                         | Hussein Yapit, Ashwin Shrinivas                                            |                                     | Template Version                    | v2025.01                              |

########### 1 Contents

1	WHAT	2

2	Value Proposition	2

2.1	Press release	2

2.2	Process	3

2.3	Landscape	3

2.4	Customer Persona	3

2.4.1	Customer PROFILES	3

2.5	Customer example	3

2.6	Non-Goals	3

2.7	Functional requirements	3

2.7.1	SCENARIO/TITLE 1	4

2.7.2	As a Trident DW user, I can ….	4

2.7.3	As a sensitive/key DW customer, I will ….	4

2.7.4	SCENARIO/TITLE 2	4

2.7.5	As a Trident DW user, I can ….	4

2.7.6	As a trident DW user, I can ….	5

2.7.7	customer facing Metrics	5

2.8	ai USAGE/INTEGRATION POINTS	5

2.9	Non-functional requirements	5

3	Components	5

4	Feature Usage TELEMETRY	6

4.1	Top-level metrics	6

4.2	Usability/Funnel	6

4.3	Customer Success Criteria	6

5	t-sql surface area	7

5.1	&lt;T-SQL&gt;	7

5.1.1	category	7

5.1.2	Requirements	7

5.1.3	Impacts/challenges	7

6	Supportability	7

6.1	TSG	7

6.2	Telemetry	7

6.3	Troubleshooter	7

6.4	DMV	7

6.5	Monitoring	7

6.6	error messages	8

6.7	Self-help	8

7	Marketing plan	8

7.1	Goals of marketing plan &amp; Customer Perception	8

7.2	Promotion plan	8

8	OPEN ITEMS	8

9	REVISION HISTORY	9

10	APPENDIX	9

## 1 WHAT

OneLake Security is a foundational security framework integrated across Microsoft Fabric workloads to provide a **single, consistent, and centralized security model for data access—especially for read operations—within OneLake storage.** It enables customers to enforce unified security policies across diverse compute engines such as Lakehouses and SQL Endpoints, eliminating the need to replicate or reconfigure security rules for the same data across multiple environments.

**Why OneLake Security?**

In modern analytics ecosystems, data is often accessed simultaneously by different compute engines and users with varying permission needs. Without a unified model, customers face significant complexity and risk:

- **Security Duplication:** Customers must manually replicate row-level security (RLS), column-level security (CLS), and masking policies across multiple workloads, leading to inconsistencies and governance gaps.

- **Governance Overhead:** Managing multiple disjoint security configurations increases administrative burden, audit complexity, and the chance of privilege escalation or data leaks.
- **Cross-Workload Collaboration Challenges:** Sharing data securely across workspaces or teams requires duplicative access controls or complicated external sharing setups.

**What OneLake Security Provides**

OneLake Security **enforces a single source of truth for data read permissions, driven by ownership-based access control enforced at query runtime.** This means:

- When users query data through any supported workload, whether directly on a Lakehouse or via SQL Endpoint shortcuts, OneLake Security ensures that **the source artifact’s access control policies are always honored.**
- Row-level filters, column masking, and fine-grained access rules are applied uniformly and transparently, preventing unauthorized access regardless of the entry point.
- The model supports **two operational modes** to accommodate customer needs and compatibility requirements:
    - 1.1. **Delegated  Mode:** The workload relies solely on SQL-level permissions; OneLake Security is bypassed for read operations. Customers who require full SQL compatibility or have legacy policies use this mode. In summary, this is the existing patterns, with small changes to honor now data ownership for shortcuts.
    - 1.2. **OneLake Security Mode:** Read access to data tables is governed entirely by OneLake Security policies, while write and management operations remain controlled through the Lakehouse Engine. This hybrid approach allows customers to benefit from centralized read security without disrupting existing SQL security models.

**Benefits to Customers**

- **Simplified Security Management:** Customers define and manage data read access policies in a single place, reducing risk and administrative effort.
- **Consistent Enforcement:** Security policies are consistently applied, preventing accidental privilege escalations or data exposure across compute engines.
- **Seamless Collaboration:** Enables secure data sharing and cross-workspace access without complex replication or external sharing.
- **Scalable Governance:** The ownership-based model aligns naturally with large-scale enterprise data estates where multiple workloads and teams co-exist.

**Competitive Differentiation**

Unlike many platforms that require separate security models per compute engine or manual synchronization of security policies, OneLake Security provides a **unified, transparent enforcement mechanism integrated into OneLake’s storage layer and Fabric’s query engines.** This approach minimizes security drift and operational complexity, positioning Microsoft Fabric as a leader in secure, scalable data governance.

## 2 Value Proposition

OneLake Security solves the problem of managing consistent and fine-grained data access across multiple compute workloads that share data in OneLake. Without it, customers face duplicated security policies, complex administration, and risks of data leaks or inconsistent governance. By providing a single, centralized security layer native to OneLake storage, it ensures that access controls like row-level and column-level security are applied uniformly, no matter which workload or query method is used.

What makes OneLake Security unique is its ownership-based enforcement model that applies policies at query runtime, combined with flexible modes that let customers adopt centralized security gradually or keep SQL-based controls when needed. Unlike competitors that require separate security configurations per compute engine, OneLake Security integrates deeply with Microsoft Fabric’s identity and permission systems to simplify governance and reduce the risk of security gaps across large, multi-workload environments.

For customers, this means easier security management, stronger protection of sensitive data, and smoother collaboration across teams and workloads. Policies are defined once and enforced everywhere, reducing overhead and improving compliance. Users can securely share data across workspaces without duplicating policies or data, and enjoy consistent access controls whether they query data in Lakehouses, SQL Endpoints, or BI tools. Overall, OneLake Security delivers unified, scalable security that helps enterprises confidently govern and scale their data ecosystems.

### 2.1 Blog or Press release

With the release of OneLake Security, SQL Endpoint now enables customers to enforce a unified, centralized security model for data access across all workloads within OneLake. This means row-level security, column masking, and fine-grained access policies defined once are consistently applied whenever data is queried through SQL Endpoint, eliminating the need to duplicate security configurations and reducing governance complexity. By integrating deeply with OneLake’s ownership-based enforcement, SQL Endpoint provides a seamless, secure experience that simplifies administration and strengthens data protection across diverse analytics environments.

### 2.2 Process

Customers configure OneLake Security by selecting an **access mode** on the SQL Analytics Endpoint settings within the Fabric portal. Two modes are available:

- **User Identity Mode:** Enforces data access using the signed-in user’s Entra ID. OneLake performs permission checks directly based on roles defined at the Lakehouse level. SQL-level GRANT/REVOKE on tables is ignored, and security policies like RLS and CLS are centrally managed. Writes are not allowed via SQL Endpoint in this mode, and Admin/Member/Contributor roles bypass OneLake security—only Viewers or read-only shares are governed.
- **Delegated Identity Mode:** Uses the artifact owner’s identity to access data in OneLake. All access is governed through SQL permissions (GRANT, RLS, CLS, DDM). OneLake roles are not enforced for reads. This mode supports legacy models and full T-SQL security features.

When switching modes, SQL permissions or OneLake roles are activated/deactivated accordingly. User Identity Mode enables a **Security Sync** service that translates OneLake roles and policies into SQL database role structures, including support for secure shortcut access where the source Lakehouse’s policies are enforced.

**Success metrics** include User Identity Mode adoption rate, reduction in security misconfigurations, sync reliability, and governance efficiency. Metrics will be tracked via telemetry and support trends.

### 2.3 Landscape

&lt; *Who are our competitors and* w *hat are they doing?  Why are our customers asking…...&gt;*

### 2.4 Customer Persona

#### 2.4.1 Customer PROFILES

| ![spec-image](Images/spec-onelake-security-sql-endpoint-for-markdown-2/image_1.png)   | Jasmin  **Big Data Resource Manager**  Manage big data resources for a team. Coordinate, reallocate or provide data resources (storage or compute) as needed.   |
|---------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|

| ![spec-image](Images/spec-onelake-security-sql-endpoint-for-markdown-2/image_2.png)   | Anna  **Data Analyst**  Frame a business problem; Analyze data to help leaders make business decisions.   |
|---------------|-----------------------------------------------------------------------------------------------------------|

Source: [Data to Insights Personas](https://hits.microsoft.com/collection/7002530)

### 2.5 Customer example

A large enterprise with strict regulatory and internal governance requirements is centralizing its analytics workloads in Microsoft Fabric. Their data platform is structured using a **medallion architecture** , where raw ingestion occurs in **Bronze** , curated and cleaned data is refined in **Silver** , and business-ready views are exposed in **Gold** . Multiple departments—including Compliance, Risk, and Marketing—consume this data through Power BI, notebooks, and SQL Endpoints, each with distinct access needs.

Previously, enforcing consistent row- and column-level security across these layers required duplicating logic in SQL views or maintaining separate security policies for each tool. This approach was brittle, error-prone, and failed to provide a clear audit trail for external regulators or internal reviewers. Teams often struggled to ensure that security followed the data as it progressed through the medallion layers.

With **OneLake Security in User Identity mode** , the organization defines all access controls—including **RLS and CLS** —centrally in the Lakehouse. These policies automatically apply across the **entire medallion flow** , regardless of whether data is accessed at the Bronze, Silver, or Gold layer. For example, personally identifiable information (PII) may be accessible in Silver only to authorized compliance users, and fully anonymized in Gold for broader business use—enforced by OneLake policies, not duplicated SQL logic.

Security Sync ensures these controls remain consistent and up to date, even when data is exposed through **shortcuts** in downstream Lakehouses or SQL Endpoints. This architecture enables the enterprise to scale their governance model confidently, knowing that **data access policies move with the data** —from raw to refined—across the entire Fabric ecosystem. It simplifies operations, improves compliance reporting, and ensures that governance is tightly aligned with the lifecycle of the data

### 2.6 Non-Goals

This feature is focused on enabling **centralized read-access enforcement** for structured data in OneLake when accessed through SQL Analytics Endpoints. The following items are explicitly **out of scope** for OneLake Security enforcement in this context:

1. **Write operations:** OneLake Security does not govern write patterns. All write operations are controlled through workspace roles and are executed via the Lakehouse UI or other compute engines.
2. **SQL object governance:** OneLake Security is not designed to manage access to SQL objects such as **stored procedures** , **views** , or **functions** . These objects remain governed by standard SQL permissions (e.g., GRANT EXECUTE) defined within the SQL Endpoint.
3. **Transactional guarantees:** This feature does not support transactional consistency between OneLake role definitions and SQL enforcement. Policy updates are propagated asynchronously through the Security Sync service.
4. **Least privilege enforcement:** OneLake Security follows a **most-permissive-wins** model. If a user belongs to multiple roles, the role that grants the broadest access will take precedence, even if other roles impose restrictions.
5. **Metadata sync conflict resolution:** This feature does not address metadata synchronization issues caused by external schema changes (e.g., dropped columns used in CLS). Such errors may interrupt policy propagation but are not resolved automatically by this system.
6. **Policy management UI:** This feature does not provide a dedicated user experience for managing OneLake Security roles or policies. Configuration is handled by the **OneLake UX** , and SQL Endpoint surfaces only the enforcement behavior.
7. **Dynamic Data Masking (DDM):** DDM is not supported under OneLake Security. It remains a SQL-only feature available in Delegated Identity mode.
8. **Encryption:** OneLake Security does not provide encryption controls or integrate with encryption frameworks. Data encryption at rest and in transit is handled separately by the OneLake platform.
9. **File-based access paths:** OneLake Security only applies to structured data accessed via **TDS connections** through SQL Endpoints. Any direct access to files (e.g., via Spark or REST APIs) is governed independently by OneLake’s storage-level access controls.

### 2.7 Functional requirements

#### 2.7.1 Functional Behavior: Setting OneLake Security Mode for SQL Endpoint

**Objective** Allow Admins and Members to configure the **Data Access Mode** (User Identity or Delegated Identity) for a SQL Endpoint directly from the Fabric UX, with clear guidance and proper access validation.

| **ID**   | **Requirement**                                                                                                                                                                                 | **Priority**   |
|----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------|
| FR-001   | I, as a user with Admin or Member role in the workspace, can change the Data Access Mode of a SQL Endpoint through the Settings menu in the Fabric Web Experience for SQL Endpoint              | P0             |
| FR-002   | When accessing the Settings > Security section of a SQL Endpoint, I can view the current Data Access Mode and see both options: User Identity and Delegated Identity.                           | P0             |
| FR-003   | Before confirming a change in mode, I receive a clear guidance tooltip or dialog explaining the differences between the two modes, their implications, and scenarios where each is recommended. | P0             |
| FR-004   | Only Admin or Member roles can change the mode. Contributors and Viewers should not see the option to change the Data Access Mode.                                                              | P0             |
| FR-005   | A change in mode triggers a confirmation prompt with a short explanation and link to documentation for deeper understanding.                                                                    | P1             |
| FR-006   | After changing the mode, the setting is applied persistently and can be validated via a UX                                                                                                      | P0             |
| FR-007   | The Data Access Mode must be scoped per SQL Endpoint (i.e., changing the mode on one endpoint does not affect others in the same or different workspace).                                       | P0             |
| FR-008   | Telemetry is captured when a change is made, including who changed the setting, when, and what the new mode is—for audit purposes.                                                              | P1             |

#### 2.7.2 Functional Behaviors for Security Sync in OneLake Security for SQL Endpoints

**Objective** This section defines the **functional expectations of Security Sync** when operating under **User Identity Mode** for SQL Endpoints integrated with OneLake Security. The intent is to describe what users—specifically those with **Admin permissions** —can expect when configuring roles, permissions, and security constructs (e.g., CLS, RLS, OLS) through the **OneLake security panel** (Lakehouse experience), and how those configurations are reflected and enforced within the SQL Endpoint environment.

| **ID**   | **Requirement**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | **Priority**   |
|----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------|
| SS-001   | I, as an Admin, can define RLS, CLS, and OLS roles in the OneLake security panel, and expect them to appear as database roles in the SQL Endpoint with corresponding scope and purpose.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | P0             |
| SS-002   | I, as an Admin, can assign users or groups to OneLake-defined security roles and expect those assignments to be reflected as database role memberships in SQL.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | P0             |
| SS-003   | I, as an Admin, can remove users or delete roles in the OneLake panel and expect those changes to be removed from SQL roles within two minutes.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | P0             |
| SS-004   | I, as an Admin, understand that OneLake Security governs only SELECT (read) permissions. It does not enforce write operations such as INSERT, UPDATE, or DELETE. These must be managed separately through SQL permissions.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | P0             |
| SS-005   | I, as an Admin, understand that Security Sync operates only after Metadata Sync succeeds. If metadata sync fails due to schema mismatches or other issues, the security sync step will be skipped, and I will be notified with a clear message.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | P0             |
| SS-006   | I, as an Admin, understand that if metadata changes (e.g., column drops or renames) invalidate a CLS or RLS rule, the sync process will fail with an error that includes the rule name and affected column, and I will be responsible for resolving the inconsistency.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | P0             |
| SS-007   | I, as an Admin, understand that certain errors (e.g., stale metadata, invalid rule logic, or missing dependencies) may prevent the evaluation of security policies. I will receive a clear message naming the affected rule and be guided to fix it or contact support.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | P0             |
| SS-008   | I, as an Admin, expect that if Security Sync fails due to internal system issues (e.g., unhandled exceptions or service downtime), the error will include a correlation ID and direct me to open a support case.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | P0             |
| SS-009   | I, as an Admin, understand that if I attempt to force a security sync on an artifact in Delegated Mode, the system will block the operation and inform me that force sync is not supported in this mode.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | P0             |
| SS-010   | I, as an Admin, understand that if I attempt to manually GRANT or DENY SELECT on tables governed by OneLake Security, I will receive an error that the permission is managed by OneLake and cannot be altered via T-SQL.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | P0             |
| SS-011   | I, as an Admin, can grant permissions via T-SQL to views, stored procedures, or functions, as those are not governed by OneLake Security.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | P0             |
| SS-012   | I, as an Admin, can expect the system to consistently notify me when errors occur, clearly stating whether I need to take action (e.g., fix metadata or rule definition) or escalate via a support case.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | P0             |
| SS-013   | I, as an Admin, understand that OneLake Security is the source of truth for governed tables, and changes made directly in SQL (e.g., adding or removing users from governed roles) may be blocked or overwritten by sync.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | P1             |
| SS-014   | I, as an Admin, expect that sync behavior is scoped per artifact, and policies only apply to SQL Endpoints that access a given Lakehouse directly or via shortcut.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | P0             |
| SS-015   | I, as an Admin, understand that when a long-running operation (such as a bulk insert or update) is active on a table governed by OneLake Security, a Security Sync attempt may be delayed until the operation completes. I will be informed of the blocking session(s), and will have the option to either wait, cancel the conflicting operations manually, or retry using a  **Force Sync**  option that terminates blocking queries automatically.                                                                                                                                                                                                                                                                                                                                                                   | P0             |
| SS-016   | ~~I, as an Admin, understand that when a CLS, RLS, or DDM policy is broken due to table or column renames, the table will be blocked for impacted roles or users, and I will receive a call-to-action in the side panel to~~  ~~**trigger a retry operation**~~  ~~. The retry will perform a~~  ~~**policy-schema realignment check**~~  ~~, and if alignment is successful (e.g., policy and schema are now valid), access will be~~  ~~**automatically restored**~~  ~~.~~  I, as an Admin, understand that when a CLS, RLS, or DDM policy is broken due to table rename operation, column rename or column drop operation, the table will be blocked for impacted roles or users, and I will receive a call-to-action in the side panel with details of the error, including police, table name and missing column. | P0             |
| SS-017   | I, as an Admin, understand that when a CLS, RLS, or DDM policy is broken due to table or  **column renames or column drops**  **, I must fix the security polices affected by this rename operation**  , and once fixed, I can retry security sync to unblock the table access.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | P0             |
| SS-018   | I, as an Admin, expect SQL Endpoint to support at least the same maximum number of security roles as supported by OneLake Security. SQL Endpoint must never impose a lower role capacity limit than OneLake for any artifact.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | P0             |
| SS-019   | I, as an Admin, expect Security Sync to successfully project and maintain all OneLake-defined roles in SQL without truncation, silent omission, failure, or degradation when the number of roles approaches the maximum supported by OneLake.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | P0             |
| SS-020   | I, as an Admin, expect role membership assignments (users, groups, and service principals) to scale proportionally with the number of supported roles without causing sync instability, metadata overflow, or SLA regression                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | P0             |
| SS-021   | I, as an Admin, expect that role scale limits in SQL are aligned with OneLake Security capacity and validated as part of GA readiness to ensure SQL Endpoint never becomes the limiting factor for security definition.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | P0             |
| SS-022   |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | P0             |
| SS-023   | I, as an Admin, understand that security roles generated and managed by OneLake Security (OneSecurity) cannot be deleted, altered, or renamed via T-SQL. Any attempt to DROP ROLE, ALTER ROLE, or modify such roles must be blocked by the SQL engine with a clear error message stating that the role is system-managed by OneLake Security.                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | P0             |
| SS-024   | I, as an Admin, expect that OneLake-managed roles are protected at the engine level and are not dependent on naming conventions (e.g., prefixes) for identification or protection.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | P0             |
| SS-025   |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | P0             |

I, as an Admin, expect that all OneLake-defined security roles and their memberships are **fully projected and enforced in the SQL Endpoint within a maximum SLA of 5 minutes** after a valid Security Sync trigger, even when operating at maximum supported role capacity.

I, as an Admin, expect SQL Endpoint to support full OneLake role names without artificial length restrictions introduced by projection or prefixing mechanisms. SQL must support the maximum role name length allowed by OneLake Security without truncation or workaround prefixes.

#### 2.7.3 Functional Behavior: Onelake security and shortcut behavior for sql endpoints on sso mode

**Objective** To ensure **source-enforced security** for all data accessed via **shortcuts** in SQL Endpoints under **User Identity Mode (SSO)** . These requirements define the **functional expectations** for how metadata changes, access patterns, and view chaining behave when the data is **owned by another artifact** and accessed through a shortcut.

The system must ensure that **no security policies are bypassed at the destination artifact** , all **permissions are evaluated at the source** , and **errors are surfaced consistently** when shortcuts are broken or misaligned.

| **Shortcut Metadata Change Requirements**                        |                                                                                                                                                                                                                                                                                                                                        |              |
|------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------|
| **ID**                                                           | **Requirement**                                                                                                                                                                                                                                                                                                                        | **Priority** |
| ASV-001                                                          | I, as an Admin, understand that when the  **Artifact Shortcut Version**  of any shortcut changes, the entire SQL Endpoint enters single-user mode, cancels all in-flight queries, and resumes automatically once the update completes.                                                                                                 | P0           |
| ASV-002                                                          | I, as an Admin, expect the  **Artifact Shortcut Version update process completes in under 2 minutes**  , and that the SQL Endpoint returns to multi-user mode automatically, without requiring manual intervention.                                                                                                                    | P0           |
| ASV-003                                                          | I, as an Admin, when a  **column is added**  to a source table referenced by a shortcut, expect that ongoing queries remain unaffected, and the new column appears in subsequent metadata refreshes. Security enforcement continues normally unless new policies reference the added column.                                           | P0           |
| ASV-004                                                          | I, as an Admin, when a  **column is dropped**  from a source table referenced by a shortcut, and the column is referenced in a view or policy, I expect queries to fail with a message identifying the missing column and affected objects or policies.                                                                                | P0           |
| ASV-005                                                          | I, as an Admin, when a  **column is renamed**  , and the old name is used in a policy or object, I expect queries to fail until those references are updated. The rename  **does trigger an Artifact Shortcut Version change**  .                                                                                                      | P0           |
| ASV-006                                                          | I, as an Admin, when the  **shortcut target URL is changed**  , I expect this to trigger an Artifact Shortcut Version update, all queries to be canceled, and a message surfaced that the shortcut was modified and must be revalidated.                                                                                               | P0           |
| ASV-007                                                          | I, as an Admin, can expect  **clear error messages and visibility in Object Explorer or Monitoring**  , explaining that the system is applying metadata or Artifact Shortcut Version updates.                                                                                                                                          | P1           |
| ASV-008                                                          | I, as an Admin, understand that  **shortcut metadata mismatches will not propagate inconsistently**  —either the query executes fully, or it fails entirely with  **all-or-nothing semantics**  if security evaluation is incomplete.                                                                                                  | P0           |
| ASV-009                                                          | I, as an Admin, expect that once the Artifact Shortcut Version update completes, the SQL Endpoint will serve queries using refreshed metadata and enforce updated security policies from the source artifact.                                                                                                                          | P0           |
| ASV-010                                                          | I, as an Admin, when the  **name of a shortcut table is changed**  at the source, expect all existing queries and references (including views) in the destination artifact to fail. A clear error must indicate that the shortcut is broken due to a rename, and security policies cannot be evaluated until the reference is updated. | P0           |
| **View, Function, and Stored Procedure Behavior with Shortcuts** |                                                                                                                                                                                                                                                                                                                                        |              |
| **ID**                                                           | **Requirement**                                                                                                                                                                                                                                                                                                                        | **Priority** |
| SC-VW-001                                                        | I, as an Admin, understand that when a view, stored procedure, or function references shortcut-backed tables, ownership chaining is disabled, and OneLake Security is evaluated per user identity across all referenced shortcuts.                                                                                                     | P0           |
| SC-VW-002                                                        | I, as an Admin, when a user executes a view, stored procedure, or function that references shortcut-backed tables, the query is blocked if the user lacks access to any of the referenced shortcuts—even if they have access to the object itself (e.g., EXEC proc).                                                                   | P0           |
| SC-VW-003                                                        | I, as an Admin, when a view or function mixes shortcut-backed and local tables, the system must still apply all-or-nothing security: access is granted only if the user has access to all referenced tables, including the shortcut ones.                                                                                              | P0           |
| SC-VW-004                                                        | I, as an Admin, expect that when a shortcut reference is nested inside a view or called function (directly or indirectly), OneLake Security is still enforced, and if the user lacks permission on the shortcut data, the outermost query is blocked with a clear message.                                                             | P0           |
| SC-VW-005                                                        | I, as an Admin, cannot override or bypass OneLake Security on a shortcut by creating a view or function at the destination artifact—source ACLs remain the authoritative security mechanism, even if the destination artifact owner has elevated permissions.                                                                          | P0           |

#### 2.7.4 Functional Behavior: Onelake security and IntelliSense behavior for user identity mode.

**Objective** This section defines the expected behavior of IntelliSense when writing T-SQL statements in SQL Endpoints governed by **OneLake Security under User Identity Mode** . It captures how IntelliSense helps users avoid invalid or blocked security operations by providing **real-time, context-aware feedback** when read permissions (SELECT) are controlled by OneLake.

In User Identity Mode, OneLake Security acts as the **single source of truth** for read permissions, including RLS, CLS, and OLS rules. SQL users cannot override these rules using T-SQL commands like GRANT, DENY, or ALTER ROLE. IntelliSense acts as the first line of defense, surfacing guidance **before the query is executed** , reducing frustration, and helping users align with organizational security policies.

|    |    |    |
|----|----|----|
|    |    |    |

#### 2.7.5 Functional Behavior: Onelake security in delegated mode

**Objective**

This section defines the expected behaviors for **SQL Endpoints operating in Delegated Mode** , specifically when accessing data through **OneLake shortcuts** . In this mode:

- Security is enforced exclusively via **SQL-layer permissions**
- **RLS, CLS, and OLS defined in OneLake Security are not honored**
- **Security Sync is not triggered or required**
- **User identity is not evaluated** — queries execute under the **artifact identity**
| **ID**   | **Requirement**                                                                                                                                                                                  | **Priority**   |
|----------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------|
| DM-001   | I, as an Admin, understand that RLS, CLS, and OLS defined in OneLake Security are ignored in Delegated Mode.                                                                                     | P0             |
| DM-002   | I, as an Admin, can GRANT SELECT, INSERT, UPDATE, DELETE on individual tables, schemas, and columns using standard T-SQL.                                                                        | P0             |
| DM-003   | I, as an Admin, can GRANT EXECUTE permissions on views, stored procedures, and functions, and these are respected at runtime under artifact identity.                                            | P0             |
| DM-004   | I, as an Admin, can create SQL-based Row-Level Security (RLS) using CREATE SECURITY POLICY, FILTER PREDICATE, and bind them to tables.                                                           | P0             |
| DM-005   | I, as an Admin, can create Column-Level Security (CLS) using MASKED WITH FUNCTION or similar SQL mechanisms.                                                                                     | P0             |
| DM-006   | I, as an Admin, can define Object-Level Security by controlling visibility through T-SQL DENY, GRANT, and REVOKE operations on views, tables, functions, and stored procedures.                  | P0             |
| DM-007   | I, as an Admin, can create custom database roles, assign users or service principals (SPNs), and use those roles to scope access.                                                                | P0             |
| DM-008   | I, as an Admin, can use built-in SQL roles (e.g., db_datareader, db_datawriter) and assign them as needed using ALTER ROLE.                                                                      | P0             |
| DM-009   | I, as an Admin, can create views and procedures that include logic for authorization, filtering, or abstraction layers. These will be honored during execution.                                  | P0             |
| DM-010   | I, as an Admin, can GRANT/DENY VIEW DEFINITION on any database object to control metadata visibility.                                                                                            | P1             |
| DM-011   | I, as an Admin, understand that metadata visibility is not filtered by OneLake CLS policies; any masking or restriction must be handled through SQL.                                             | P1             |
| DM-012   | I, as an Admin, can configure external access rules, network isolation, and private link, and these apply regardless of Delegated Mode.                                                          | P1             |
| DM-013   | I, as an Admin, understand that shortcut-based tables execute using artifact identity, and OneLake ACLs and security policies are bypassed.                                                      | P0             |
| DM-014   | I, as an Admin, understand that switching a SQL Endpoint from User Identity Mode to Delegated Mode does not immediately invalidate existing query caches. Security state may be inconsistent.    | P0             |
| DM-015   | I, as an Admin, expect that after switching to Delegated Mode, a mechanism exists to clear caches or reinitialize the SQL Endpoint to reflect accurate delegated access.                         | P0             |
| DM-016   | I, as an Admin, expect that all data access under Delegated Mode strictly abides by the artifact identity’s permissions. SQL Endpoint cannot return data the identity cannot access directly.    | P0             |
| DM-017   | I, as an Admin, understand that Delegated Mode treats SQL Endpoint as a third-party engine and restricts access to reflect only what the delegated identity is authorized to access.             | P0             |
| DM-018   | I, as an Admin, expect that switching to Delegated Mode ensures shortcut traversal only succeeds if the artifact identity has explicit access to the source artifact and table.                  | P0             |
| DM-019   | I, as an Admin, can prevent exposure of restricted shortcut data in Delegated Mode by managing permissions on the source artifact (e.g., revoking access from the artifact identity).            | P0             |
| DM-020   | I, as an Admin, understand that historical access patterns from prior modes (e.g., User Identity Mode) do not carry forward in Delegated Mode. Only current permissions are honored.             | P0             |
| DM-021   | I, as an Admin, understand that Delegated Mode introduces a clear separation between data access evaluation (based on artifact identity) and control plane actions (e.g., publishing artifacts). | P0             |
| DM-022   | I, as an Admin, can expect the SQL Endpoint in Delegated Mode to never fallback or revalidate using user identity, even when errors occur, preserving access boundaries.                         | P0             |

#### 2.7.6 Force Security Sync – Handling Blocking Conditions and Forced Policy Application

**Objective**

This section defines the expected behavior when Security Sync cannot complete due to blocking conditions such as active table locks, long-running sessions, or background processes preventing policy enforcement.
SqlDatabaseInSingleUserMode

The intent is to ensure administrators have full transparency and control to override these blocking conditions through Force Security Sync—a nuclear operation that terminates all active queries and sessions across the workspace to immediately reapply pending security policies.

These requirements guarantee that Security Sync never remains indefinitely stalled, that administrators are clearly informed of the impact before action, and that all activities are properly logged for auditability.

| **ID**   | **Requirement**                                                                                                                                                                                                                                                                                                           | **Priority**   |
|----------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------|
| FSS-1    | As a user with  **Admin/Member/Contributor (A/M/C)**  permissions, when  **Security Sync**  cannot complete because a lock or another background process is preventing policy application for over 5 seconds, the system must surface an inline error dialog indicating that Security Sync is blocked and cannot proceed. | P0             |
| FSS-2    | The error dialog must explicitly identify the blocking condition when available (e.g., “Security Sync is blocked by an active session or service lock on table [table_name]”)                                                                                                                                             | P0             |
| FSS-3    | The dialog must present two actions:  **Force Security Sync (Terminate All In-Flight Queries)   Cancel and Wait**  .                                                                                                                                                                                                      | P0             |
| FSS-4    | If the user selects  **Force Security Sync (Terminate All In-Flight Queries)**  , the system must:  1) cancel  **all active user queries and sessions**  across the affected workspace,  2) forcibly release all locks, and  3) immediately re-execute Security Sync to apply pending security policies.                  | P0             |
| FSS-5    | Before executing Force Sync, the system must display a  **confirmation warning**  clearly stating the impact: “This action will cancel all active queries and sessions across this workspace and may cause workload disruption. Proceed?”                                                                                 | P0             |
| FSS-6    | If the user selects  **Cancel and Wait**  , Security Sync stops gracefully, leaving all locks and sessions intact. The dialog must provide the session IDs or blocking object references for investigation.                                                                                                               | P0             |
| FSS-7    | If, between the time the error dialog appears and the user confirms Force Sync, the blocking condition is resolved naturally (e.g., locks are released, background service completes), the system must  **skip query termination**  and proceed with Security Sync normally.                                              | P0             |
| FSS-8    | Users with  **Viewer or ReadData**  permissions must never see the Force Security Sync option. If visible but disabled, a tooltip must explain: “Only Admin, Member, or Contributor roles can force Security Sync.”                                                                                                       | P0             |
| FSS-9    | Force Security Sync must be auditable. The action, triggering user, timestamp, and affected sessions must be logged in the Security or Audit Log for traceability.                                                                                                                                                        | P1             |

#### 2.7.7 System-Wide Requirements (All Modes)

**Objective**

This section outlines the foundational behaviors and platform-wide expectations that apply regardless of the SQL Endpoint access mode (User Identity or Delegated). These requirements govern how administrators assign security permissions, interpret identity types, and manage access at both the data plane (SQL layer) and control plane (workspace and artifact level).

These behaviors are enforced consistently across all Microsoft Fabric SQL Endpoints to ensure clarity, security, and manageability of data access—regardless of how OneLake Security is configured.

| **ID**      | **Requirement / Capability**                                                                                                                                                            | **Priority**   |
|-------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------|
| **SYS-001** | I, as an Admin, understand that  **no distinction is made between UPNs, SPNs, or AAD groups**  when assigning SQL roles—T-SQL supports all identity types equally.                      | P0             |
| **SYS-002** | I, as an Admin, understand that  **control plane permissions**  (e.g., Workspace Contributor or Admin) are still required to  **connect to the SQL Endpoint and configure security**  . | P0             |
| **SYS-003** | I, as an Admin, understand that  **SQL-layer permissions only govern data access**  , and must be  **configured independently from workspace-level access**  .                          | P0             |
| **SYS-004** | I, as an Admin, understand that  **new SQL Endpoints default to User Identity Mode**  , while  **existing artifacts remain in Delegated Mode unless explicitly changed**  .             | P0             |

#### 2.7.8 UX Considerations for Setting Security (Both Modes)

While this document focuses on **Delegated Mode functional behavior** , it is equally important to offer intuitive user experience across both modes (Delegated and User Identity), to create a streamlined experience to set security when defining polices for instance with T-SQL. We recognize that:

- Admins must be able to **visually identify the mode** of each SQL Endpoint
- Security configuration UIs must **clearly guide the user** through valid actions depending on the mode
- **Error feedback, permission visibility, and policy mappings** should adapt to the context (e.g., show SQL roles for Delegated; OneLake roles for User Identity)

**Note** : The design and UX specification for managing security across modes is **out of scope for this document** . For full guidance and proposed UX patterns, please refer to: [SQL Security UX Functional Spec.docx](https://microsoft-my.sharepoint.com/:w:/p/fresantos/EWmCz1ID0T9AvEjrv4ACcQYB1V77j9p162iyVuezyhIk8A?e=nDgo85)

#### 2.7.9 SCENARIO/TITLE 1

*&lt;For each requirement in the table above, create a detailed use case in this section. Please ensure your feature works across the following scenarios:*

1. *Security*
2. *Fabric Warehouse web editor*
3. *Fabric SQL endpoint web editor*
4. *Metadata Sync*
5. *Warehouse / SQL Endpoint Copilot*
6. *Monitoring*
7. *CI/CD*
8. *IntelliSense*
9. *Client tools*
10. *Migration*
11. *QI/DMVs*

*The feature is not complete if the above is not done&gt;*

#### 2.7.10 As a Trident DW user, I can use the feature in the Fabric Warehouse Editor

*&lt;Describe how a customer will use the scenario in the Fabric UX as much detail as possible, using tables, graphics, screen shots, mock ups etc., to convey as complete a picture as possible on the desired functionality.*

*For example considerations for the Fabric Warehouse UX,  are, across SQL endpoint and Warehouse*

- *Security*
- *Query Execution*
- *Results Pane*
- *Syntax Highlighting does NOT warn about an error*
- *MD Sync and SQL endpoint working with the feature*

*Some features that make the experience useable are:*

- *Intellisense*
- *Syntax Highlighting*
- *Templates*

*For example, alter table should execute without error, provide results you can see in the results or data preview, and is improved with intellisense, syntax highlighting and templates in the ribbon and object explorer.*

#### 2.7.11 As a Trident DW user, I can ….

*&lt;Describe the scenario in as much detail as possible, using tables, graphics, screen shots, mock ups etc., to convey as complete a picture as possible on the desired functionality&gt;*

#### 2.7.12 As a Trident DW user, I can ….

*&lt;Describe the scenario in as much detail as possible, using tables, graphics, screen shots, mock ups etc., to convey as complete a picture as possible on the desired functionality&gt;*

#### 2.7.13 As a Trident DW user, I can ….

*&lt;Describe the scenario in as much detail as possible, using tables, graphics, screen shots, mock ups etc., to convey as complete a picture as possible on the desired functionality&gt;*

#### 2.7.14 As a Trident DW user, I can ….

*&lt;Describe the scenario in as much detail as possible, using tables, graphics, screen shots, mock ups etc., to convey as complete a picture as possible on the desired functionality&gt;*

#### 2.7.15 As a sensitive/key DW customer, I will ….

*&lt;Describe the scenario in as much detail as possible, using tables, graphics, screen shots, mock ups etc., to convey as complete a picture as possible on the desired functionality&gt;*

#### 2.7.16 SCENARIO/TITLE 2

#### 2.7.17 As a Trident DW user, I can ….

*&lt;Describe the scenario in as much detail as possible, using tables, graphics, screen shots, mock ups etc., to convey as complete a picture as possible on the desired functionality&gt;*

#### 2.7.18 As a trident DW user, I can ….

*&lt;Describe the scenario in as much detail as possible, using tables, graphics, screen shots, mock ups etc., to convey as complete a picture as possible on the desired functionality&gt;*

#### 2.7.19 customer facing Metrics

&lt;Depending on the feature, describe the metrics needed for customers to gain insights into feature usage (how it relates to query performance, consumption of storage or resources, etc…).  Metrics should be surfaced in appropriate interfaces such as Portal or Studio.  Experiences for the entire metrics ecosystem should be accounted for, including exhausting of metrics to Log Analytics.  QI/DMVs and catalog views should be spec’d out as well for appropriate behaviors and intuitive column naming that has been broadly reviewed and signed off on.&gt;

### 2.8 ai USAGE/INTEGRATION POINTS

&lt;Think about how AI/co-pilots could be used or integrated into your feature and scenarios.  AI may not make sense in every case, and if you believe integration of AI capabilities would not be applicable, that’s fine.  Update this section with your proposed approach for AI in the context of feature usage and/or why AI is or is not applicable&gt;

### 2.9 Non-functional requirements

&lt;Depending on the scope of this feature, it can have some form of an early release to validate with and collect feedback from customers. Each cell describes the exit criteria for the milestone for each scenario&gt;

|          |          |                 |                 |                |            |
|----------|----------|-----------------|-----------------|----------------|------------|
|          |          | **Milestone**   |                 |                |            |
|          |          | Private Preview | Private Preview | Public Preview | GA         |
| Scenario | Scenario | 03/23/2025      | 03/23/2025      | 09/01/2025     | 11/17/2025 |

## 3 Components This Feature Touches

*&lt;In this section, you should list all of the components that the feature will use or touch in order to function.  This allows visibility for the entire team into what could potentially be impacted by the feature/changes and will help us to identify dependencies earlier in the process.  An example table is provided below, please update as appropriate for your feature.&gt;*

**NOTE: There is no SQL engine feature that does not have a front-end component. Use the below to help you think through the I can statements above.**

| Feature                   | Component                        | Description                                                                                                                             |
|---------------------------|----------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------|
| Core Product Scenarios    | Security                         |                                                                                                                                         |
|                           | Fabric SQL DW web editor         |                                                                                                                                         |
|                           | Fabric SQL endpoint web editor   |                                                                                                                                         |
|                           | Metadata Sync                    |                                                                                                                                         |
|                           | Warehouse / SQL Endpoint Copilot |                                                                                                                                         |
|                           | Monitoring                       |                                                                                                                                         |
|                           | CI/CD                            |                                                                                                                                         |
|                           | IntelliSense                     |                                                                                                                                         |
|                           | Client tools                     |                                                                                                                                         |
|                           | Migration                        |                                                                                                                                         |
|                           | QI/DMVs                          |                                                                                                                                         |
|                           | Security                         |                                                                                                                                         |
| EXAMPLE; ALTER TABLE      | Warehouse SQL Editor             | Query Execution                                                                                                                         |
|                           | Warehouse SQL Editor             | Intellisense                                                                                                                            |
|                           | Warehouse SQL Editor             | Syntax Highlighting                                                                                                                     |
|                           | Warehouse OE                     | OE Templates                                                                                                                            |
|                           | Warehouse Ribbon                 | Ribbon Templates                                                                                                                        |
|                           | Web Git Integration              | Surface Area                                                                                                                            |
|                           | Web Deployment Pipelines         | Surface Area                                                                                                                            |
|                           | SQL Database Projects            | Surface Area                                                                                                                            |
|                           | VSCode                           | Query Execution                                                                                                                         |
|                           | SSMS                             | Query Execution                                                                                                                         |
|                           | VSCode                           | Intellisense                                                                                                                            |
|                           | SSMS                             | Intellisense                                                                                                                            |
|                           | VSCode                           | Syntax highlighting                                                                                                                     |
|                           | SSMS                             | Syntax highlighting                                                                                                                     |
|                           | SQL Database Projects            | Validation                                                                                                                              |
|                           | SQL Database Projects            | Deployment                                                                                                                              |
| Querying DBX delta tables | OneLake/shortcuts                | User creates shortcut to folder with Delta table                                                                                        |
|                           | Table discovery                  | Discovery process adds new metadata from Delta log if needed.                                                                           |
|                           | UQO                              | Potential performance improvements (dynamic file pruning for example, support for bloom filters, support for delta file level stats, …) |
|                           | Transcoder                       | Read arbitrary parquet files                                                                                                            |

## 4 Feature Usage TELEMETRY

&lt;Feature Usage Telemetry should be captured for each requirement to inform user behavior and adoption. Over time, telemetry metrics should evolve into KPIs or be leveraged for supportability scenarios.  This is the business focused telemetry that should be captured for each feature.&gt;

### 4.1 Top-level metrics

To evaluate the success of OneLake Security across SQL Endpoints (DW and SQLEP), we will focus on usage adoption, operational stability, governance enforcement, and customer sentiment. These criteria aim to capture both the technical effectiveness and the real-world impact of the feature across enterprise scenarios.

**1. Adoption and Usage**

- We will monitor the percentage of SQL Endpoints operating in **User Identity Mode** versus Delegated Mode. A rising share of artifacts in User Identity Mode will signal customer adoption of OneLake-governed security practices.
- Additional adoption indicators include the number of SQL artifacts (Warehouses, Lakehouses, Endpoints) with **OneLake-defined security roles and policies applied** , such as RLS, CLS, or OLS.

**2. Stability and Sync Health**

- The success of **Security Sync operations** will be measured by the percentage that complete without errors. This reflects the overall robustness of the policy translation layer from OneLake to SQL.
- We will track the **average propagation time** of security changes from OneLake to SQL Endpoints, with a target of under two minutes. This ensures timely enforcement of policy changes.

**3. Customer Satisfaction and Support Signals**

- Customer experience will be measured by the **number of ICMs and Support cases** related to OneLake Security. A decrease over time, especially post-GA, is an indicator of maturity and clarity in behavior.
- Positive adoption trends, such as customers opting into User Identity Mode for net-new deployments, will reflect trust in the default security model.

### 4.2 Usability/Funnel

*&lt;This section is a bit more tactical and may be very feature specific.  For this section, you really want to concentrate on usability metrics and and conditions that potentially lead to further adoption or abandonment.  Again, describe metrics in terms of human language sentences.*

*Ex: What error conditions are contributing to customer abandonment and/or increasing customer churn?  How discoverable is the feature and what are the main sources of discovery?  Are there leading indicators of feature abandonment?  Does this feature have a higher adoption rate among a certain segment?&gt;*

- MAU/DAU/WAU customer discovery through adoption
- How discoverable is the feature
- How used is the feature
- Abandonment rate
- Where do customers find or ‘enter’ the feature (UX, ADF, Dataflows, Gen 2, SSIS, etc.)
- Errors and error rates

## 5 t-sql surface area

Ideally, capabilities align with [Transact-SQL Reference (Database Engine](https://docs.microsoft.com/en-us/sql/t-sql/language-reference?view=azure-sqldw-latest) standards to maintain user experience parity.  Note the menu structure on the left as it categorizes the T-SQL commands and data types.  For example, under Queries, you would find SELECT and within that you would find SELECT – GROUP BY.

*&lt;For each feature, we should consider what, if any changes need to be made to the existing/standard T-SQL surface area.  Include what User Interfaces (SSMS/SSDT, Trident Portal etc.), APIs and TSQL is needed to expose this functionality including examples of each statement, error messages and a note about impacts and challenges to future migration of Gen2/Serverless&gt;*

### 5.1 &lt;T-SQL&gt;

#### 5.1.1 category

&lt;example: Queries -&gt; SELECT -&gt;SELECT-GROUP BY&gt;

#### 5.1.2 Requirements

&lt;include examples, permissions needed and definition for items like QI/DMVs or System Catalogs&gt;

#### 5.1.3 Impacts/challenges

## 6 Supportability

All but the smallest features need to clone the Supportability Requirements ADO work item in [SU\_INF005 Fabric DW Feature Overview Template | Trident DW TSGs (eng.ms)](https://eng.ms/docs/cloud-ai-platform/azure-data/azure-data-intelligence-platform/synapse-dw/trident-dw-top-level-service/trident-dw/supportability/infs/su_inf005_fabricdwfeatureoverviewtemplate) to drive/track the following work.

### 6.1 TSG

Specify the new, primary TSG location that will provides an overview of the feature.  The overview should be cloned from [SU\_INF005 Fabric DW Feature Overview Template | Trident DW TSGs (eng.ms)](https://eng.ms/docs/cloud-ai-platform/azure-data/azure-data-intelligence-platform/synapse-dw/trident-dw-top-level-service/trident-dw/supportability/infs/su_inf005_fabricdwfeatureoverviewtemplate) .

### 6.2 Telemetry

- Specify the questions you’ll want to ask to determine if the primary points of this feature’s algorithm are functioning properly.
- Specify existing MDS table(s) or new table(s) that will store the telemetry to answer these questions.  Ensure new telemetry has appropriate foreign key(s) for required joins.
- During private/public preview, for each aforementioned telemetry question, specify the exact Kusto query that provides the answer.  If the telemetry can’t answer such, enhance it before GA.

### 6.3 Troubleshooter

A proper subset of each component’s telemetry questions should be added to the Synapse SQL Troubleshooter (SST).  Specify which section of SST will be enhanced and what info will be presented (and which chart types will be used).

### 6.4 DMV

Specify what user facing telemetry will be supported via DMV(s).  This is usually a subset of the aforementioned backend telemetry.

### 6.5 Monitoring

Specify the Live Site Incident (LSI) Alerts that are needed.

### 6.6 error messages

Ensure the user facing error messages are clear and actionable.  Ensure Code Markers are used for all error messages.

### 6.7 Self-help

Specify what customer facing Self-Help updates are needed.  During private/public preview, PM &amp; Dev should define the common usability issues, as Self-Help is the last ability to help the customer help themselves before creating a Service Request.

## 7 Marketing plan

### 7.1 Goals of marketing plan &amp; Customer Perception

&lt; *How do you plan to measure reach across channels, things like: number of impressions, number of likes, number of reposts, sentiment analysis of comments&gt;*

### 7.2 Promotion plan

&lt; *Your promotion plan will likely span several weeks or even months and goes beyond the release blog and may even start prior to actual feature launch.  The below table is a list of ideas to get you started, but is by no means meant to be fully inclusive.  Be creative!  The more you talk about your feature, the more others will as well.&gt;*

| PROMOTION PLAN                | PROMOTION PLAN   | PROMOTION PLAN   | PROMOTION PLAN   | PROMOTION PLAN    |
|-------------------------------|------------------|------------------|------------------|-------------------|
| CHANNEL                       | Y/N              | CONTENT NEEDED   | OWNER            | TIMING            |
| LinkedIn                      | Y                | Y                | Freddie Santos   | 09/01/2025 – PuPr |
| Blog                          | Y                | Y                | Freddie Santos   | 09/01/2025 – PuPr |
| YouTube                       | Y                | Y                | Freddie Santos   | 09/01/2025 – PuPr |
| Webinar                       |                  |                  |                  |                   |
| Podcast                       |                  |                  |                  |                   |
| Reddit                        |                  |                  |                  |                   |
| Medium                        |                  |                  |                  |                   |
| Public Docs                   | Y                | Y                | Freddie Santos   | 09/01/2025 – PuPr |
| Fabric Blog                   | Y                | Y                | Freddie Santos   | 09/01/2025 – PuPr |
| What’s New                    | Y                | Y                | Freddie Santos   | 09/01/2025 – PuPr |
| Fabric Insiders               | Y                | Y                | Freddie Santos   | 09/01/2025 – PuPr |
| Weekly Fabric/Synapse Compete |                  |                  |                  |                   |
| CSA Virtual Lunch             |                  |                  |                  |                   |
| MVPs                          | Y                | Y                | Freddie Santos   | 09/01/2025 – PuPr |

## 8 OPEN ITEMS

|   No. | Item   | Owner   | Resolution   |
|-------|--------|---------|--------------|
|     1 |        |         |              |
|     2 |        |         |              |
|     3 |        |         |              |

## 9 REVISION HISTORY

| Date       | Author         | Comment                                                                                                 |
|------------|----------------|---------------------------------------------------------------------------------------------------------|
| 11/13/2025 | Freddie Santos | Added Force Security Sync Requirements on section 2.7.6                                                 |
| 11/07/2025 | Freddie Santos | Updated Requirements around Rename and Drop Columns to streamline user experience.                      |
| 08/07/2025 | Freddie Santos | Update to Spec Template and consolidation of multiple One Pagers in a Single Spec for easy readability. |

## 10 APPENDIX

The items below are Specs and Documentations from Partner workloads and support documents for OneLake Security.

- [Universal Security Spec](https://microsoft.sharepoint.com/:w:/t/DataCloud/EUOQNNr9VDlJnW758h6gZGQB_skPorauAsLK0ST_IG872g?e=pkCMDu)
- [Universal Security Visualization with examples](https://microsoft-my.sharepoint.com/:p:/p/chweb/Eew-gQGBH49JjjopSDxzkhwBw76en7w9ncymORI0ktRg1A?e=InFh9d)
- [Create a Unity Catalog metastore - Azure Databricks | Microsoft Learn](https://learn.microsoft.com/en-us/azure/databricks/data-governance/unity-catalog/create-metastore)
- [Google BigLake and Dataplex capabilities](https://cloud.google.com/blog/products/data-analytics/automate-data-governance-with-google-cloud-dataplex-and-biglake)
- [Detailed Spreadsheet considering USec across SQL and OneLake](https://microsoft.sharepoint.com/:x:/t/AzureSQLDataWarehouse/EQ6uie8fbWtCq0XilEv94iEBWcJDYR82Ke-sgqf82r6JVQ?e=I8ekgC)
- [Trident DW Universal Security One Pager](https://microsoft.sharepoint.com/:w:/t/AzureSQLDataWarehouse/EWQxHqIGJMlMulMsm3pBwIAB_30karNkPElB19PLmnLh1g?e=eRV3w5)
- [SQL Security UX Functional Spec.docx](https://microsoft-my.sharepoint.com/:w:/p/fresantos/EWmCz1ID0T9AvEjrv4ACcQYB1V77j9p162iyVuezyhIk8A?e=nDgo85)