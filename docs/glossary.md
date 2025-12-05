# Plan Glossary

## Systems

### Self-Service Portal
A user-facing channel where end users submit initial request data.  
The automation does not interact with the portal directly; it serves only as the upstream origin of the payload later obtained from CRM.

### CRM Platform
A centralized case-management system that stores, structures, and governs service requests.  
It provides the process trigger (case identifier) and is also the endpoint for final updates, results, and human handover.

### Address Directory
An authoritative lookup service containing validated address records used for data normalization.  
It is accessed in a read-only manner to deliver deterministic matches or signal ambiguity during enrichment.

### Configuration Database
A controlled repository of reference entities, configuration items, and normalized business attributes.  
It is the primary target system into which validated and transformed payload data is written.

### RPA Process Automation
The orchestration component executing deterministic logic across all participating systems.  
It holds no business data; instead, it coordinates retrieval, validation, enrichment, transformation, and posting steps.


## data validation

### Provenance 
The record of where a piece of data came from, how it was produced, and which systems transformed it.

