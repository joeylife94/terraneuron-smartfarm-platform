package com.terraneuron.ops.repository;

import com.terraneuron.ops.entity.RefreshTokenSession;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.Optional;

@Repository
public interface RefreshTokenSessionRepository extends JpaRepository<RefreshTokenSession, Long> {

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select session from RefreshTokenSession session where session.tokenId = :tokenId")
    Optional<RefreshTokenSession> findByTokenIdForUpdate(@Param("tokenId") String tokenId);

    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("""
            update RefreshTokenSession session
               set session.revokedAt = :revokedAt,
                   session.revokeReason = :reason,
                   session.updatedAt = :revokedAt
             where session.familyId = :familyId
               and session.revokedAt is null
            """)
    int revokeActiveFamily(
            @Param("familyId") String familyId,
            @Param("revokedAt") Instant revokedAt,
            @Param("reason") String reason);
}
