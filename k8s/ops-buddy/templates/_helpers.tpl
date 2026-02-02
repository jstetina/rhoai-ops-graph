{{/*
Expand the name of the chart.
*/}}
{{- define "ops-buddy.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "ops-buddy.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "ops-buddy.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "ops-buddy.labels" -}}
helm.sh/chart: {{ include "ops-buddy.chart" . }}
{{ include "ops-buddy.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "ops-buddy.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ops-buddy.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "ops-buddy.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "ops-buddy.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Image pull secrets
*/}}
{{- define "ops-buddy.imagePullSecrets" -}}
{{- if .Values.global.imagePullSecret }}
imagePullSecrets:
  - name: {{ include "ops-buddy.fullname" . }}-pull-secret
{{- end }}
{{- end }}

{{/*
Component-specific image
*/}}
{{- define "ops-buddy.image" -}}
{{- $registry := .root.Values.global.imageRegistry -}}
{{- $repository := .component.image.repository -}}
{{- $tag := .component.image.tag | default "latest" -}}
{{- if $repository -}}
{{- printf "%s:%s" $repository $tag -}}
{{- else -}}
{{- printf "%s/%s:%s" $registry .defaultRepo $tag -}}
{{- end -}}
{{- end }}
