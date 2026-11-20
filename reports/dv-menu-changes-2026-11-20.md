# Spotfire Data Virtualization: changes to the help menu, 20 Nov 2026

For the Data Virtualization documentation team. No topic's text was changed; this is about where topics sit in the menu and which repeated copies are published once.

**Why.** Data Virtualization ships five separate help systems (Adapters, Business Directory, Deployment Manager, Studio, Web UI). Published side by side on the new site they gave five top-level entries all titled with the product name, four copies of What's New, folders repeated inside themselves (`deployment-manager/deployment-manager`, `business-directory/businessdirectory/business-directory`), 76 adapters in one flat list, and dozens of topics published twice. They are now one menu with 11 sections, the same in every version.

**Old addresses.** Every page that moved, and every copy no longer published, redirects to its new place, so bookmarks and links from outside keep working. The Japanese help for 8.8.0 and 8.8.1 follows the English layout page for page.


## Version 8.9.0

### The new menu

1. **What's New** (section page: the former "What’s New" page, `whats-new.md`)
     - "Spotfire® Data Virtualization", now titled "Key New Features"
2. **Getting Started** (section page: the former "Spotfire® Data Virtualization" page, `user-guides.md`)
     - Getting Started Guide
     - Tutorial Guide
3. **Installation and Upgrade Guide** (section page: the former "Installation and Upgrade Guide" page, `user-guides/installation-upgrade-guide.md`)
     - "Installation and Upgrade Guide": this wrapper level is removed; its chapters move up one level
4. **Using Studio** (a new section page)
     - User Guide
     - Discovery Guide
5. **Web UI** (section page: the former "SDV Web UI" page, `web-ui/sdv-web-ui.md`)
     - "SDV Web UI": this wrapper level is removed; its chapters move up one level
6. **Adapters** (a new section page)
     - **Relational Databases** (new group): SDV DB2 Adapter, SDV Greenplum Adapter, SDV HSQLDB Adapter, SDV Informix Adapter, SDV Microsoft Access Adapter, SDV Microsoft Access Adapter(non-odbc), SDV MySQL Adapter, SDV NeoView Adapter, SDV Netezza Adapter, SDV Oracle Adapter, SDV PostgreSQL Adapter, SDV SAP HANA Adapter, SDV SingleStore Adapter, SDV SQL Server Adapter, SDV Sybase Adapter, SDV Teradata Adapter, SDV Vertica Adapter, SDV DataDirect Mainframe Adapter, SDV Composite Adapter
     - **Cloud Data Warehouses** (new group): SDV Amazon Redshift Adapter, SDV Google BigQuery Adapter, SDV Snowflake Adapter
     - **Big Data, NoSQL and Streaming** (new group): SDV Drill Adapter, SDV HBase Adapter, SDV Apache HBase Adapter, SDV Hive Adapter, SDV Impala Adapter, SDV SparkSQL Adapter, SDV ComputeDB Adapter, SDV Cassandra Adapter, SDV CosmosDB Adapter, SDV Couchbase Adapter, SDV Amazon DynamoDB Adapter, SDV Elasticsearch Adapter, SDV MarkLogic Adapter, SDV MongoDB Adapter, SDV Splunk Adapter, SDV Streaming Adapter
     - **Files and Cloud Storage** (new group): SDV File Data Sources, SDV Local File Storage Adapter, SDV Amazon S3 Adapter, SDV Azure Data Lake Adapter, SDV Google Cloud Storage Adapter
     - **Enterprise Applications** (new group): Using the Oracle E Business Suite Adapter, SDV NetSuite Adapter, Using the Salesforce.com Adapter, SDV Salesforce with SSO Adapter, Using the SAP for SDV Adapter, Using SAP BW with SDV, Using SAP BW BEx with SDV, Using Siebel with SDV, SDV Microsoft DynamicsCRM Adapter, SDV Microsoft DynamicsGP Adapter, SDV Microsoft DynamicsNAV Adapter, SDV SharePoint Adapter, SDV Active Directory Adapter
     - **SaaS, Marketing and Social** (new group): SDV Google Ads Adapter, SDV Google Analytics Adapter, SDV Google Calendar Adapter, SDV Google Contacts Adapter, SDV Google Directory Adapter, SDV Google Drive Adapter, SDV Google Sheets Adapter, SDV HubSpot Adapter, SDV Marketo Adapter, SDV OracleEloqua Adapter, SDV Facebook Adapter, SDV Twitter Adapter, SDV Email Adapter, SDV RSS Adapter
     - **Web Services and Custom Sources** (new group): SDV Web Based Data Sources, SDV OData Adapter, SDV JDBC-ODBC Bridge Adapter, SDV Custom Java Procedures
7. **Business Directory** (section page: the former "BusinessDirectory" page, `business-directory/businessdirectory.md`)
     - "Spotfire® Data Virtualization": this wrapper level is removed; its chapters move up one level
     - "BusinessDirectory": this wrapper level is removed; its chapters move up one level
     - Install Business Directory
     - Business Directory Introduction
     - Using Business Directory
     - Business Directory API and System Tables
     - Business Directory REST API
8. **Administration and Security** (a new section page)
     - Administration Guide
     - Security Features Guide
     - "ActiveCluster", now titled "ActiveCluster Guide"
     - Troubleshooting
9. **Client Interfaces and APIs** (a new section page)
     - Client Interfaces Guide
     - Application Programming Interface Guide
     - Data Source Toolkit Guide
10. **Reference Guide** (section page: the former "Reference Guide" page, `user-guides/reference-guide.md`)
     - "Reference Guide": this wrapper level is removed; its chapters move up one level
11. **Documentation, Support and Legal** (a new section page)
     - Spotfire Documentation and Support Services
     - Legal and Third-Party Notices

### Topics published once

- **Deployment Manager help (40 pages):** it is the same text as the Administration Guide's Deployment Manager chapter, so only the Administration Guide copy is published. Each Deployment Manager page redirects to its twin there.
- **Other repeated copies (14):** identical text in two places. The copy kept and the copy that now redirects to it:

| No longer published | Redirects to |
|---|---|
| Spotfire® Data Virtualization (`business-directory.md`) | Spotfire® Data Virtualization (`adapters.md`) |
| Whats New (`web-ui/whats-new.md`) | What’s New (`whats-new.md`) |
| What’s New in SDV 8.9 (`business-directory/whats-new-in-sdv-8-9.md`) | What's New (`user-guides/whats-new-2.md`) |
| Apache Drill Data Source Limitations (`user-guides/user-guide/configuring-relational-data/data-source-limitations/apache-drill-data-source-limitations.md`) | Apache Drill Data Source Limitations (`adapters/sdv-drill-adapter/apache-drill-data-source-limitations.md`) |
| DB2 and DB2 z/OS Data Source Limitations (`user-guides/user-guide/configuring-relational-data/data-source-limitations/db2-db2-z-os-data-source.md`) | DB2 and DB2 z/OS Data Source Limitations (`adapters/sdv-db2-adapter/db2-and-db2-z-os-data-source-limitations.md`) |
| Hive Compatible Data Source Limitations (`user-guides/user-guide/configuring-relational-data/data-source-limitations/hive-compatible-data-source.md`) | Hive Compatible Data Source Limitations (`adapters/sdv-hive-adapter/hive-compatible-data-source-limitations.md`) |
| Netezza Data Source Limitations (`user-guides/user-guide/configuring-relational-data/data-source-limitations/netezza-data-source-limitations.md`) | Netezza Data Source Limitations (`adapters/sdv-netezza-adapter/netezza-data-source-limitations.md`) |
| Oracle Data Source Limitations (`user-guides/user-guide/configuring-relational-data/data-source-limitations/oracle-data-source-limitations.md`) | Oracle Data Source Limitations (`adapters/sdv-oracle-adapter/oracle-data-source-limitations.md`) |
| Teradata Data Source Introspection (`user-guides/user-guide/configuring-relational-data/data-source-limitations/teradata-data-source-introspection.md`) | Teradata Data Source Introspection (`adapters/sdv-teradata-adapter/teradata-data-source-introspection.md`) |
| Vertica Data Source Limitations (`user-guides/user-guide/configuring-relational-data/data-source-limitations/vertica-data-source-limitations.md`) | Vertica Data Source Limitations (`adapters/sdv-vertica-adapter/vertica-data-source-limitations.md`) |
| Connecting to SQL Server datasource using an Active directory Login (`user-guides/user-guide/configuring-relational-data/connecting-sql-server-datasource-using-active.md`) | Connecting to SQL Server datasource using an Active directory Login (`adapters/sdv-sql-server-adapter/connecting-sql-server-datasource-using-active.md`) |
| Netezza Caching Tips from an Expert (`user-guides/user-guide/sdv-caching/cache-requirements-and-limitations/netezza-caching-tips-from-an-expert.md`) | Netezza Caching Tips from an Expert (`adapters/sdv-netezza-adapter/netezza-data-source-limitations/netezza-caching-tips-from-an-expert.md`) |
| Spotfire® Data Virtualization (`adapters.md`) | Spotfire® Data Virtualization (`user-guides.md`) |
| What's New (`user-guides/whats-new-2.md`) | What’s New (`whats-new.md`) |

### For the writers to decide (not changed)

These pairs are nearly the same but differ in a way only a writer can settle. Both copies are still published.

- **Changing the Repository Password** / **Changing the Repository Password**: Two words: BD says 'SDV' and '<SDV_install_dir>', Admin Guide says 'Spotfire' and '<TDV_install_dir>'. Recommend keep both (each guide's own procedure).
- **Tips from an Expert if the Server Does Not Start** / **Tips from an Expert if the Server Does Not Start**: Install Guide copy is fuller: one extra sentence (server.properties is reread when composite.sh monitor restarts the server), 'locations', '<BD_install_dir>'. BD copy says 'the SDV server'. Recommend keep both.
- **Microsoft SQL Server 2008 Limitation** / **Microsoft SQL Server 2008 Limitation**: java.security path differs: adapter '<TDV_install_dir>\conf\server\security\java.security', User Guide '<TDV_install_dir>/jdk/conf/security/java.security'. A writer should say which is right; then drop the other.
- **SAP HANA Data Source Limitations and Characteristics** / **SAP HANA Data Source Limitations and Characteristics**: Adapter copy keeps stale PDF page numbers in two link texts (', page 218', ', page 219'); otherwise same. Recommend drop the User Guide copy -> adapter copy (as for the other limitations pages) and accept the page numbers, or keep both.

## Version 8.8.1

### The new menu

1. **What's New** (section page: the former "What's New" page, `whats-new.md`)
2. **Getting Started** (section page: the former "TIBCO® Data Virtualization" page, `user-guides.md`)
     - Getting Started Guide
     - Tutorial Guide
3. **Installation and Upgrade Guide** (section page: the former "Installation and Upgrade Guide" page, `user-guides/installation-upgrade-guide.md`)
     - "Installation and Upgrade Guide": this wrapper level is removed; its chapters move up one level
4. **Using Studio** (a new section page)
     - User Guide
     - Discovery Guide
5. **Web UI** (section page: the former "TDV Web UI" page, `web-ui/tdv-web-ui.md`)
     - "TDV Web UI": this wrapper level is removed; its chapters move up one level
     - Introduction
     - Data Catalog
     - Data Workbench
6. **Adapters** (a new section page)
     - **Relational Databases** (new group): TDV DB2 Adapter, TDV Greenplum Adapter, TDV HSQLDB Adapter, TDV Informix Adapter, TDV Microsoft Access Adapter, TDV Microsoft Access Adapter(non-odbc), TDV MySQL Adapter, TDV NeoView Adapter, TDV Netezza Adapter, TDV Oracle Adapter, TDV PostgreSQL Adapter, TDV SAP HANA Adapter, TDV SingleStore Adapter, TDV SQL Server Adapter, TDV Sybase Adapter, TDV Teradata Adapter, TDV Vertica Adapter, TDV DataDirect Mainframe Adapter, TDV Composite Adapter
     - **Cloud Data Warehouses** (new group): TDV Amazon Redshift Adapter, TDV Google BigQuery Adapter, TDV Snowflake Adapter
     - **Big Data, NoSQL and Streaming** (new group): TDV Drill Adapter, TDV HBase Adapter, TDV Apache HBase Adapter, TDV Hive Adapter, TDV Impala Adapter, TDV SparkSQL Adapter, ComputeDB Adapter, TDV Cassandra Adapter, TDV CosmosDB Adapter, TDV Couchbase Adapter, TDV Amazon DynamoDB Adapter, TDV Elasticsearch Adapter, TDV MarkLogic Adapter, TDV MongoDB Adapter, TDV Splunk Adapter, TIBCO Streaming Adapter
     - **Files and Cloud Storage** (new group): TDV File Data Sources, TDV Local File Storage Adapter, TDV Amazon S3 Adapter, TDV Azure Data Lake Adapter, TDV Google Cloud Storage Adapter
     - **Enterprise Applications** (new group): Using the Oracle E Business Suite Adapter, TDV NetSuite Adapter, Using the Salesforce.com Adapter, TDV Salesforce with SSO Adapter, Using the SAP for TDV Adapter, Using SAP BW with TDV, Using SAP BW BEx with TDV, Using Siebel with TDV, TDV Microsoft DynamicsCRM Adapter, TDV Microsoft DynamicsGP Adapter, TDV Microsoft DynamicsNAV Adapter, TDV SharePoint Adapter, TDV SharePoint ExcelServices Adapter, TDV Active Directory Adapter
     - **SaaS, Marketing and Social** (new group): TDV Google Ads Adapter, TDV Google Analytics Adapter, TDV Google Calendar Adapter, TDV Google Contacts Adapter, TDV Google Directory Adapter, TDV Google Drive Adapter, TDV Google Sheets Adapter, TDV HubSpot Adapter, TDV Marketo Adapter, TDV OracleEloqua Adapter, TDV Facebook Adapter, TDV Twitter Adapter, TDV Email Adapter, TDV RSS Adapter
     - **Web Services and Custom Sources** (new group): TDV Web Based Data Sources, TDV OData Adapter, TDV JDBC-ODBC Bridge Adapter, TDV Custom Java Procedures
7. **Business Directory** (section page: the former "BusinessDirectory" page, `business-directory/businessdirectory.md`)
     - "TIBCO® Data Virtualization": this wrapper level is removed; its chapters move up one level
     - "BusinessDirectory": this wrapper level is removed; its chapters move up one level
     - Install Business Directory
     - Business Directory Introduction
     - Using Business Directory
     - Business Directory API and System Tables
     - Business Directory REST API
8. **Administration and Security** (a new section page)
     - Administration Guide
     - Security Features Guide
     - "ActiveCluster", now titled "ActiveCluster Guide"
     - Troubleshooting
9. **Client Interfaces and APIs** (a new section page)
     - Client Interfaces Guide
     - Application Programming Interface Guide
     - Data Source Toolkit Guide
10. **Reference Guide** (section page: the former "Reference Guide" page, `user-guides/reference-guide.md`)
     - "Reference Guide": this wrapper level is removed; its chapters move up one level
11. **Documentation, Support and Legal** (a new section page)
     - TIBCO Documentation and Support Services
     - Legal and Third-Party Notices

### Topics published once

- **Deployment Manager help (42 pages):** it is the same text as the Administration Guide's Deployment Manager chapter, so only the Administration Guide copy is published. Each Deployment Manager page redirects to its twin there.
- **Other repeated copies (18):** identical text in two places. The copy kept and the copy that now redirects to it:

| No longer published | Redirects to |
|---|---|
| TIBCO® Data Virtualization (`business-directory.md`) | TIBCO® Data Virtualization (`user-guides.md`) |
| TIBCO® Data Virtualization (`adapters.md`) | TIBCO® Data Virtualization (`user-guides.md`) |
| TIBCO® Data Virtualization (`web-ui.md`) | TIBCO® Data Virtualization (`user-guides.md`) |
| What's New (`user-guides/whats-new-3.md`) | What's New (`whats-new.md`) |
| What's New (`business-directory/whats-new.md`) | What's New (`whats-new.md`) |
| What's New (`web-ui/whats-new-4.md`) | What's New (`whats-new.md`) |
| DB2 and DB2 z/OS Data Source Limitations (`user-guides/user-guide/configuring-relational/data-source-limitations/db2-db2-z-os-data-source.md`) | DB2 and DB2 z OS Data Source Limitations (`adapters/tdv-db2-adapter/db2-and-db2-z-os-data-source-limitations.md`) |
| Apache Drill Data Source Limitations (`user-guides/user-guide/configuring-relational/data-source-limitations/apache-drill-data-source-limitations.md`) | Apache Drill Data Source Limitations (`adapters/tdv-drill-adapter/apache-drill-data-source-limitations.md`) |
| Hive Compatible Data Source Limitations (`user-guides/user-guide/configuring-relational/data-source-limitations/hive-compatible-data-source-limitations.md`) | Hive Compatible Data Source Limitations (`adapters/tdv-hive-adapter/hive-compatible-data-source-limitations.md`) |
| Netezza Data Source Limitations (`user-guides/user-guide/configuring-relational/data-source-limitations/netezza-data-source-limitations.md`) | Netezza Data Source Limitations (`adapters/tdv-netezza-adapter/netezza-data-source-limitations.md`) |
| Netezza Caching Tips from an Expert (`user-guides/user-guide/tdv-caching/cache-requirements-and-limitations/netezza-caching-tips-from-an-expert.md`) | Netezza Caching Tips from an Expert (`adapters/tdv-netezza-adapter/netezza-data-source-limitations/netezza-caching-tips-from-an-expert.md`) |
| Oracle Data Source Limitations (`user-guides/user-guide/configuring-relational/data-source-limitations/oracle-data-source-limitations.md`) | Oracle Data Source Limitations (`adapters/tdv-oracle-adapter/oracle-data-source-limitations.md`) |
| Connecting to SQL Server datasource using an Active directory Login (`user-guides/user-guide/configuring-relational/connecting-sql-server-datasource-using-active.md`) | Connecting to SQL Server datasource using an Active directory Login (`adapters/tdv-sql-server-adapter/connecting-sql-server-datasource-using-active.md`) |
| Teradata Data Source Introspection (`user-guides/user-guide/configuring-relational/data-source-limitations/teradata-data-source-introspection.md`) | Teradata Data Source Introspection (`adapters/tdv-teradata-adapter/teradata-data-source-introspection.md`) |
| Vertica Data Source Limitations (`user-guides/user-guide/configuring-relational/data-source-limitations/vertica-data-source-limitations.md`) | Vertica Data Source Limitations (`adapters/tdv-vertica-adapter/vertica-data-source-limitations.md`) |
| user-guides/tibco-documentation-and-support-services.md (`user-guides/tibco-documentation-and-support-services.md`) | TIBCO Documentation and Support Services (`tibco-documentation-and-support-services.md`) |
| business-directory/legal-and-third-party-notices.md (`business-directory/legal-and-third-party-notices.md`) | Legal and Third-Party Notices (`legal-and-third-party-notices.md`) |
| user-guides/legal-and-third-party-notices.md (`user-guides/legal-and-third-party-notices.md`) | Legal and Third-Party Notices (`legal-and-third-party-notices.md`) |

### For the writers to decide (not changed)

These pairs are nearly the same but differ in a way only a writer can settle. Both copies are still published.

- **Changing the Repository Password** / **Changing the Repository Password**: Identical in this version (in 8.9.0 two words differed and both were kept). Recommend keep both, as in 8.9.0 (each guide's own procedure); or drop the Business Directory copy -> Admin Guide.
- **Tips from an Expert if the Server Does Not Start** / **Tips from an Expert if the Server Does Not Start**: As in 8.9.0: Install Guide copy has one more sentence (server.properties reread on composite.sh monitor restart), 'locations', '<BD_install_dir>'. Recommend keep both.
- **Microsoft SQL Server 2008 Limitation** / **Microsoft SQL Server 2008 Limitation**: java.security path differs: adapter '<TDV_install_dir>\conf\server\security\java.security', User Guide '<TDV_install_dir>/jdk/conf/security/java.security'. A writer should say which is right.
- **SAP HANA Data Source Limitations and Characteristics** / **SAP HANA Data Source Limitations and Characteristics**: As in 8.9.0: adapter copy keeps stale PDF page numbers (', page 218', ', page 219') in two link texts. Recommend drop the User Guide copy -> adapter copy, or keep both.
- **business-directory/tibco-documentation-and-support-services.md** / **TIBCO Documentation and Support Services**: Off-menu copy. Only italics differ (*TDV and Business Directory Release Notes*). Recommend drop -> top-level copy.
- **web-ui/tibco-documentation-and-support-services.md** / **TIBCO Documentation and Support Services**: Off-menu copy, older wording (no Web UI User Guide in the list, 'can be found in the TIBCO Documentation site'). Recommend drop -> top-level copy.
- **web-ui/legal-and-third-party-notices.md** / **Legal and Third-Party Notices**: Off-menu copy; 'Oracle Corporation' against 'Oracle'. Recommend drop -> top-level copy.
- **deployment-manager/legal-and-third-party-notices.md** / **Legal and Third-Party Notices**: Off-menu copy; copyright 2002-2024 against 2002-2025. Recommend drop -> top-level copy.

## Version 8.8.0

### The new menu

1. **What's New** (section page: the former "What's New" page, `user-guides/whats-new-3.md`)
     - "TIBCO® Data Virtualization", now titled "Key New Features"
2. **Getting Started** (section page: the former "TIBCO® Data Virtualization" page, `user-guides.md`)
     - Getting Started Guide
     - Tutorial Guide
3. **Installation and Upgrade Guide** (section page: the former "Installation and Upgrade Guide" page, `user-guides/installation-upgrade-guide.md`)
     - "Installation and Upgrade Guide": this wrapper level is removed; its chapters move up one level
4. **Using Studio** (a new section page)
     - User Guide
     - Discovery Guide
5. **Web UI** (section page: the former "TDV Web UI" page, `web-ui/tdv-web-ui.md`)
     - "TDV Web UI": this wrapper level is removed; its chapters move up one level
     - Introduction
     - Data Catalog
     - Data Workbench
6. **Adapters** (a new section page)
     - **Relational Databases** (new group): TDV DB2 Adapter, TDV Greenplum Adapter, TDV HSQLDB Adapter, TDV Informix Adapter, TDV Microsoft Access Adapter, TDV MySQL Adapter, TDV NeoView Adapter, TDV Netezza Adapter, TDV Oracle Adapter, TDV PostgreSQL Adapter, TDV SAP HANA Adapter, TDV SingleStore Adapter, TDV SQL Server Adapter, TDV Sybase Adapter, TDV Teradata Adapter, TDV Vertica Adapter, TDV DataDirect Mainframe Adapter, TDV Composite Adapter
     - **Cloud Data Warehouses** (new group): TDV Amazon Redshift Adapter, TDV Google BigQuery Adapter, TDV Snowflake Adapter
     - **Big Data, NoSQL and Streaming** (new group): TDV Drill Adapter, TDV HBase Adapter, TDV Apache HBase Adapter, TDV Hive Adapter, TDV Impala Adapter, TDV SparkSQL Adapter, ComputeDB Adapter, TDV Cassandra Adapter, TDV CosmosDB Adapter, TDV Couchbase Adapter, TDV Amazon DynamoDB Adapter, TDV Elasticsearch Adapter, TDV MarkLogic Adapter, TDV MongoDB Adapter, TDV Splunk Adapter, TIBCO Streaming Adapter
     - **Files and Cloud Storage** (new group): TDV File Data Sources, TDV Local File Storage Adapter, TDV Amazon S3 Adapter, TDV Azure Data Lake Adapter, TDV Google Cloud Storage Adapter
     - **Enterprise Applications** (new group): Using the Oracle E Business Suite Adapter, TDV NetSuite Adapter, Using the Salesforce.com Adapter, TDV Salesforce with SSO Adapter, Using the SAP for TDV Adapter, Using SAP BW with TDV, Using SAP BW BEx with TDV, Using Siebel with TDV, TDV Microsoft DynamicsCRM Adapter, TDV Microsoft DynamicsGP Adapter, TDV Microsoft DynamicsNAV Adapter, TDV SharePoint Adapter, TDV SharePoint ExcelServices Adapter, TDV Active Directory Adapter
     - **SaaS, Marketing and Social** (new group): TDV Google Ads Adapter, TDV Google Analytics Adapter, TDV Google Calendar Adapter, TDV Google Contacts Adapter, TDV Google Directory Adapter, TDV Google Drive Adapter, TDV Google Sheets Adapter, TDV HubSpot Adapter, TDV Marketo Adapter, TDV OracleEloqua Adapter, TDV Facebook Adapter, TDV Twitter Adapter, TDV Email Adapter, TDV RSS Adapter
     - **Web Services and Custom Sources** (new group): TDV Web Based Data Sources, TDV OData Adapter, TDV JDBC-ODBC Bridge Adapter, TDV Custom Java Procedures
7. **Business Directory** (section page: the former "BusinessDiirectory" page, `business-directory/businessdiirectory.md`)
     - "TIBCO® Data Virtualization": this wrapper level is removed; its chapters move up one level
     - "BusinessDiirectory": this wrapper level is removed; its chapters move up one level
     - Install Business Directory
     - Business Directory Introduction
     - Using Business Directory
     - Business Directory API and System Tables
     - Business Directory REST API
8. **Administration and Security** (a new section page)
     - Administration Guide
     - Security Features Guide
     - "ActiveCluster", now titled "ActiveCluster Guide"
9. **Client Interfaces and APIs** (a new section page)
     - Client Interfaces Guide
     - Application Programming Interface Guide
     - Data Source Toolkit Guide
10. **Reference Guide** (section page: the former "Reference Guide" page, `user-guides/reference-guide.md`)
     - "Reference Guide": this wrapper level is removed; its chapters move up one level
11. **Documentation, Support and Legal** (a new section page)
     - TIBCO Documentation and Support Services
     - Legal and Third-Party Notices

### Topics published once

- **Deployment Manager help (43 pages):** it is the same text as the Administration Guide's Deployment Manager chapter, so only the Administration Guide copy is published. Each Deployment Manager page redirects to its twin there.
- **Other repeated copies (16):** identical text in two places. The copy kept and the copy that now redirects to it:

| No longer published | Redirects to |
|---|---|
| TIBCO® Data Virtualization (`business-directory.md`) | TIBCO® Data Virtualization (`user-guides.md`) |
| TIBCO® Data Virtualization (`adapters.md`) | TIBCO® Data Virtualization (`user-guides.md`) |
| What's New (`whats-new.md`) | What's New (`user-guides/whats-new-3.md`) |
| What's New (`business-directory/whats-new.md`) | What's New (`user-guides/whats-new-3.md`) |
| DB2 and DB2 z/OS Data Source Limitations (`user-guides/user-guide/configuring-relational/data-source-limitations/db2-db2-z-os-data-source.md`) | DB2 and DB2 z OS Data Source Limitations (`adapters/tdv-db2-adapter/db2-and-db2-z-os-data-source-limitations.md`) |
| Apache Drill Data Source Limitations (`user-guides/user-guide/configuring-relational/data-source-limitations/apache-drill-data-source-limitations.md`) | Apache Drill Data Source Limitations (`adapters/tdv-drill-adapter/apache-drill-data-source-limitations.md`) |
| Hive Compatible Data Source Limitations (`user-guides/user-guide/configuring-relational/data-source-limitations/hive-compatible-data-source-limitations.md`) | Hive Compatible Data Source Limitations (`adapters/tdv-hive-adapter/hive-compatible-data-source-limitations.md`) |
| Netezza Data Source Limitations (`user-guides/user-guide/configuring-relational/data-source-limitations/netezza-data-source-limitations.md`) | Netezza Data Source Limitations (`adapters/tdv-netezza-adapter/netezza-data-source-limitations.md`) |
| Netezza Caching Tips from an Expert (`user-guides/user-guide/tdv-caching/cache-requirements-and-limitations/netezza-caching-tips-from-an-expert.md`) | Netezza Caching Tips from an Expert (`adapters/tdv-netezza-adapter/netezza-data-source-limitations/netezza-caching-tips-from-an-expert.md`) |
| Oracle Data Source Limitations (`user-guides/user-guide/configuring-relational/data-source-limitations/oracle-data-source-limitations.md`) | Oracle Data Source Limitations (`adapters/tdv-oracle-adapter/oracle-data-source-limitations.md`) |
| Connecting to SQL Server datasource using an Active directory Login (`user-guides/user-guide/configuring-relational/connecting-sql-server-datasource-using-active.md`) | Connecting to SQL Server datasource using an Active directory Login (`adapters/tdv-sql-server-adapter/connecting-sql-server-datasource-using-active.md`) |
| Teradata Data Source Introspection (`user-guides/user-guide/configuring-relational/data-source-limitations/teradata-data-source-introspection.md`) | Teradata Data Source Introspection (`adapters/tdv-teradata-adapter/teradata-data-source-introspection.md`) |
| Vertica Data Source Limitations (`user-guides/user-guide/configuring-relational/data-source-limitations/vertica-data-source-limitations.md`) | Vertica Data Source Limitations (`adapters/tdv-vertica-adapter/vertica-data-source-limitations.md`) |
| TIBCO Documentation and Support Services (`user-guides/tibco-documentation-and-support-services.md`) | TIBCO Documentation and Support Services (`tibco-documentation-and-support-services.md`) |
| business-directory/legal-and-third-party-notices.md (`business-directory/legal-and-third-party-notices.md`) | Legal and Third-Party Notices (`legal-and-third-party-notices.md`) |
| Legal and Third-Party Notices (`user-guides/legal-and-third-party-notices.md`) | Legal and Third-Party Notices (`legal-and-third-party-notices.md`) |

### For the writers to decide (not changed)

These pairs are nearly the same but differ in a way only a writer can settle. Both copies are still published.

- **Changing the Repository Password** / **Changing the Repository Password**: Identical in this version (in 8.9.0 two words differed and both were kept). Recommend keep both, as in 8.9.0 (each guide's own procedure); or drop the Business Directory copy -> Admin Guide.
- **Tips from an Expert if the Server Does Not Start** / **Tips from an Expert if the Server Does Not Start**: As in 8.9.0: Install Guide copy has one more sentence (server.properties reread on composite.sh monitor restart), 'locations', '<BD_install_dir>'. Recommend keep both.
- **Microsoft SQL Server 2008 Limitation** / **Microsoft SQL Server 2008 Limitation**: Same text and path; the adapter copy's steps are misnumbered (first step unnumbered, then 1, 2), the User Guide copy is numbered 1-3. Recommend drop the adapter copy -> User Guide copy, or keep both.
- **SAP HANA Data Source Limitations and Characteristics** / **SAP HANA Data Source Limitations and Characteristics**: As in 8.9.0: adapter copy keeps stale PDF page numbers (', page 218', ', page 219') in two link texts. Recommend drop the User Guide copy -> adapter copy, or keep both.
- **business-directory/tibco-documentation-and-support-services.md** / **TIBCO Documentation and Support Services**: Off-menu copy. Only italics differ (*TDV and Business Directory Release Notes*). Recommend drop -> top-level copy.
- **web-ui/tibco-documentation-and-support-services.md** / **TIBCO Documentation and Support Services**: Off-menu copy, older wording (no Web UI User Guide in the list, 'can be found in the TIBCO Documentation site'). Recommend drop -> top-level copy.
- **web-ui/legal-and-third-party-notices.md** / **Legal and Third-Party Notices**: Off-menu copy; 'Oracle Corporation' against 'Oracle'. Recommend drop -> top-level copy.

## Questions for the team

1. The nearly identical pairs above: which copy is right (for example, the two java.security paths in the SQL Server 2008 limitation)?
2. The section and group names ("Using Studio", "Client Interfaces and APIs", the seven adapter groups): are they the words your readers use?
3. The 9 data-source limitation pages that were in both the User Guide and an adapter guide now live in the adapter guide only. Should the User Guide link to them instead?
