"""DICOM PS3.15 Basic Application Confidentiality Profile identifiers."""

from __future__ import annotations


# Direct identifiers and identifying workflow/device fields from the Basic
# Application Level Confidentiality Profile. Sequence contents are traversed
# recursively, and private tags are removed independently.
DICOM_PHI_KEYWORDS = frozenset(
    {
        "AccessionNumber", "AcquisitionComments", "AdmittingDate", "AdmittingDiagnosesDescription",
        "AdmittingTime", "Allergies", "ContentCreatorName", "CountryOfResidence",
        "CurrentPatientLocation", "DataSetTrailingPadding", "DerivationDescription",
        "DeviceSerialNumber", "DischargeDate", "DischargeDiagnosisDescription", "DischargeTime",
        "EthnicGroup", "FillerOrderNumberImagingServiceRequest", "HumanPerformerName",
        "InstitutionAddress", "InstitutionName", "InstitutionalDepartmentName",
        "InsurancePlanIdentification", "IntendedRecipientsOfResultsIdentificationSequence",
        "InterpretationAuthor", "InterpretationApproverSequence", "InterpretationDiagnosisDescription",
        "InterpretationIDIssuer", "InterpretationRecorder", "InterpretationText",
        "IssuerOfAdmissionID", "IssuerOfPatientID", "LastMenstrualDate", "MedicalAlerts",
        "MedicalRecordLocator", "MilitaryRank", "NameOfPhysiciansReadingStudy", "Occupation",
        "OperatorsName", "OrderCallbackPhoneNumber", "OrderEnteredBy", "OrderEntererLocation",
        "OtherPatientIDs", "OtherPatientIDsSequence", "OtherPatientNames", "PatientAddress",
        "PatientAge", "PatientBirthDate", "PatientBirthName", "PatientBirthTime", "PatientComments",
        "PatientID", "PatientInstitutionResidence", "PatientInsurancePlanCodeSequence", "PatientMotherBirthName",
        "PatientName", "PatientPrimaryLanguageCodeSequence", "PatientReligiousPreference", "PatientSex",
        "PatientSize", "PatientState", "PatientTelephoneNumbers", "PatientWeight", "PerformingPhysicianName",
        "PersonAddress", "PersonIdentificationCodeSequence", "PersonName", "PersonTelephoneNumbers",
        "PhysicianApprovingInterpretation", "PhysiciansOfRecord", "PhysiciansOfRecordIdentificationSequence",
        "PlacerOrderNumberImagingServiceRequest", "PregnancyStatus", "ProtocolName", "ReasonForStudy",
        "ReferencedPatientAliasSequence", "ReferencedPatientSequence", "ReferringPhysicianAddress",
        "ReferringPhysicianIdentificationSequence", "ReferringPhysicianName", "ReferringPhysicianTelephoneNumbers",
        "RegionOfResidence", "RequestAttributesSequence", "RequestedProcedureComments", "RequestedProcedureDescription",
        "RequestedProcedureID", "RequestingPhysician", "RequestingPhysicianIdentificationSequence",
        "RequestingService", "ResponsibleOrganization", "ResponsiblePerson", "ResultsComments",
        "ScheduledHumanPerformersSequence", "ScheduledPatientInstitutionResidence", "ScheduledPerformingPhysicianName",
        "ScheduledProcedureStepDescription", "ScheduledProcedureStepID", "ScheduledProcedureStepLocation",
        "ScheduledStationAETitle", "ScheduledStationName", "SeriesDescription", "ServiceEpisodeDescription",
        "ServiceEpisodeID", "SmokingStatus", "SpecialNeeds", "StationName", "StudyDescription", "StudyID",
        "TextComments", "TextString", "TopicAuthor", "TopicKeywords", "TopicSubject",
        "TrialName", "VisitComments",
    }
)


DICOM_UID_KEYWORDS = frozenset(
    {
        "StudyInstanceUID",
        "SeriesInstanceUID",
        "SOPInstanceUID",
        "FrameOfReferenceUID",
        "SynchronizationFrameOfReferenceUID",
        "ReferencedSOPInstanceUID",
        "ConcatenationUID",
        "IrradiationEventUID",
    }
)
