{{- define "oecophylla.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "oecophylla.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := include "oecophylla.name" . }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "oecophylla.componentName" -}}
{{- printf "%s-%s" (include "oecophylla.fullname" .root) .name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "oecophylla.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | quote }}
app.kubernetes.io/name: {{ include "oecophylla.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "oecophylla.selectorLabels" -}}
app.kubernetes.io/name: {{ include "oecophylla.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .name }}
{{- end }}

{{- define "oecophylla.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "oecophylla.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "oecophylla.secretName" -}}
{{- default (include "oecophylla.fullname" .) .Values.secrets.existingSecret }}
{{- end }}

{{- define "oecophylla.postgresHost" -}}
{{- if .Values.infrastructure.enabled }}{{ include "oecophylla.fullname" . }}-postgres{{ else }}{{ .Values.database.host }}{{ end }}
{{- end }}

{{- define "oecophylla.redisHost" -}}
{{- if .Values.infrastructure.enabled }}{{ include "oecophylla.fullname" . }}-redis{{ else }}{{ .Values.redis.host }}{{ end }}
{{- end }}

{{- define "oecophylla.kafkaBrokers" -}}
{{- if .Values.infrastructure.enabled }}{{ include "oecophylla.fullname" . }}-kafka:9092{{ else }}{{ .Values.kafka.brokers }}{{ end }}
{{- end }}

{{- define "oecophylla.databaseUrl" -}}
{{- $ssl := "" -}}
{{- if and (not .Values.infrastructure.enabled) .Values.database.sslMode -}}{{- $ssl = printf "?sslmode=%s" .Values.database.sslMode -}}{{- end -}}
{{- printf "postgres://%s:%s@%s:%v/%s%s" .Values.database.user .Values.secrets.databasePassword (include "oecophylla.postgresHost" .) .Values.database.port .Values.database.name $ssl -}}
{{- end }}

{{- define "oecophylla.redisUrl" -}}
{{- printf "redis://:%s@%s:%v/%v" .Values.secrets.redisPassword (include "oecophylla.redisHost" .) .Values.redis.port .Values.redis.database -}}
{{- end }}

{{- define "oecophylla.image" -}}
{{- if .digest -}}
{{- printf "%s@%s" .repository .digest -}}
{{- else -}}
{{- printf "%s:%s" .repository .tag -}}
{{- end -}}
{{- end }}
