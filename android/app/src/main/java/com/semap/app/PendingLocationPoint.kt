package com.semap.app

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase
import android.content.Context

@Entity(tableName = "pending_location_points")
data class PendingLocationPoint(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val sessionId: Int,
    val lat: Double,
    val lng: Double,
    val altitude: Double?,
    val speed: Double?,
    val recordedAt: String,
)

@Dao
interface PendingLocationPointDao {
    @Insert
    suspend fun insert(point: PendingLocationPoint)

    @Query("select * from pending_location_points where sessionId = :sessionId order by id limit :limit")
    suspend fun pendingForSession(sessionId: Int, limit: Int): List<PendingLocationPoint>

    @Query("delete from pending_location_points where id in (:ids)")
    suspend fun deleteByIds(ids: List<Long>)

    @Query("select count(*) from pending_location_points where sessionId = :sessionId")
    suspend fun countForSession(sessionId: Int): Int
}

@Database(entities = [PendingLocationPoint::class], version = 1, exportSchema = false)
abstract class SemapDatabase : RoomDatabase() {
    abstract fun pendingLocationPointDao(): PendingLocationPointDao

    companion object {
        @Volatile
        private var instance: SemapDatabase? = null

        fun get(context: Context): SemapDatabase {
            return instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    SemapDatabase::class.java,
                    "semap.db",
                ).build().also { instance = it }
            }
        }
    }
}
