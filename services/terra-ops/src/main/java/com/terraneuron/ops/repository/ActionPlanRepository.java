package com.terraneuron.ops.repository;

import com.terraneuron.ops.entity.ActionPlan;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

/**
 * Repository for ActionPlan entity
 */
@Repository
public interface ActionPlanRepository extends JpaRepository<ActionPlan, Long> {

    Optional<ActionPlan> findByPlanId(String planId);

    Optional<ActionPlan> findByTraceId(String traceId);

    List<ActionPlan> findByFarmIdOrderByCreatedAtDesc(String farmId);

    List<ActionPlan> findByStatusOrderByPriorityDescCreatedAtDesc(ActionPlan.PlanStatus status);

    Page<ActionPlan> findByStatus(ActionPlan.PlanStatus status, Pageable pageable);

    @Query("SELECT p FROM ActionPlan p WHERE p.status = :status AND p.farmId = :farmId ORDER BY p.priority DESC, p.createdAt DESC")
    List<ActionPlan> findByStatusAndFarmId(@Param("status") ActionPlan.PlanStatus status, @Param("farmId") String farmId);

    @Query("SELECT p FROM ActionPlan p WHERE p.status = 'PENDING' AND p.expiresAt < :now")
    List<ActionPlan> findExpiredPendingPlans(@Param("now") Instant now);

    @Query("SELECT p FROM ActionPlan p WHERE p.status = 'APPROVED' AND p.expiresAt < :now")
    List<ActionPlan> findExpiredApprovedPlans(@Param("now") Instant now);

    @Query("SELECT COUNT(p) FROM ActionPlan p WHERE p.status = :status")
    long countByStatus(@Param("status") ActionPlan.PlanStatus status);

    @Query("SELECT COUNT(p) FROM ActionPlan p WHERE p.status = 'PENDING' AND p.priority = :priority")
    long countPendingByPriority(@Param("priority") ActionPlan.ActionPriority priority);

    @Query("SELECT p FROM ActionPlan p WHERE p.farmId = :farmId AND p.createdAt BETWEEN :start AND :end ORDER BY p.createdAt DESC")
    List<ActionPlan> findByFarmIdAndDateRange(
            @Param("farmId") String farmId,
            @Param("start") Instant start,
            @Param("end") Instant end);
}
