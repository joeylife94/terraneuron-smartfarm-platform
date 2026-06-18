package com.terraneuron.ops.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Map;

/**
 * Generic CloudEvents v1.0 Envelope
 * 
 * Parses the standard CloudEvents wrapper for all cross-service events.
 * Reference: https://cloudevents.io/
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CloudEventsEnvelope<T> {
    
    @JsonProperty("specversion")
    private String specversion;
    
    @JsonProperty("type")
    private String type;
    
    @JsonProperty("source")
    private String source;
    
    @JsonProperty("id")
    private String id;
    
    @JsonProperty("time")
    private String time;
    
    @JsonProperty("datacontenttype")
    private String datacontenttype;
    
    @JsonProperty("data")
    private T data;
    
    /**
     * Validate this is a valid CloudEvents message
     * @return true if all required fields are present
     */
    public boolean isValid() {
        return specversion != null && 
               type != null && 
               source != null && 
               id != null && 
               time != null && 
               data != null;
    }
    
    /**
     * Get trace_id from data if available
     */
    @SuppressWarnings("unchecked")
    public String extractTraceId() {
        if (data instanceof Map) {
            Map<String, Object> dataMap = (Map<String, Object>) data;
            Object traceId = dataMap.get("trace_id");
            if (traceId instanceof String) {
                return (String) traceId;
            }
        }
        return null;
    }
}
