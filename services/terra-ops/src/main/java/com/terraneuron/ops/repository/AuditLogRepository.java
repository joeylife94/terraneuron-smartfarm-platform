package com.terraneuron.ops.repository;

import com.terraneuron.ops.entity.AuditLog;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;

/**
 * Repository for AuditLog entity
 */
@Repository
public interface AuditLogRepository extends JpaRepository<AuditLog, Long> {

    List<AuditLog> findByTraceIdOrderByTimestampAsc(String traceId);

    List<AuditLog> findByEntityTypeAndEntityIdOrderByTimestampAsc(String entityType, String entityId);

    Page<AuditLog> findByEventType(AuditLog.EventType eventType, Pageable pageable);

    Page<AuditLog> findByActor(String actor, Pageable pageable);

    @Query("SELECT a FROM AuditLog a WHERE a.timestamp BETWEEN :start AND :end ORDER BY a.timestamp DESC")
    Page<AuditLog> findByDateRange(@Param("start") Instant start, @Param("end") Instant end, Pageable pageable);

    @Query("SELECT a FROM AuditLog a WHERE a.success = false ORDER BY a.timestamp DESC")
    List<AuditLog> findFailedEvents(Pageable pageable);

    @Query("SELECT COUNT(a) FROM AuditLog a WHERE a.eventType = :eventType AND a.timestamp > :since")
    long countEventsSince(@Param("eventType") AuditLog.EventType eventType, @Param("since") Instant since);

    @Query("SELECT a FROM AuditLog a WHERE a.entityType = 'plan' AND a.entityId = :planId ORDER BY a.timestamp ASC")
    List<AuditLog> findPlanHistory(@Param("planId") String planId);
}
