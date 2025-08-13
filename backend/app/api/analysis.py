from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from ..data.database import get_db
from ..data.models import ScoringTypeEnum, PositionEnum
from ..data.crud import ScarcityCRUD
from ..services.evaluation import TeamEvaluator
from ..services.season_simulation import SeasonSimulator
from ..services.scarcity import ScarcityAnalyzer
from ..data.crud import TeamCRUD, DraftCRUD, PlayerCRUD
from ..data.models import Team, Draft
from sqlalchemy import text, inspect as sa_inspect

router = APIRouter()

@router.get("/team-evaluation/{team_id}")
async def evaluate_team(
    team_id: int,
    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR,
    db: Session = Depends(get_db)
):
    """
    Get comprehensive team evaluation including VORP, depth, and projections
    """
    try:
        evaluator = TeamEvaluator(db)
        evaluation = evaluator.evaluate_team(team_id, scoring_type)
        
        return evaluation
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/seed-sample-league")
async def seed_sample_league(
    team_count: int = 12,
    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR,
    db: Session = Depends(get_db)
):
    """Seed a demo league with teams, a draft, and initial picks for analysis demo."""
    try:
        # Ensure we have players to draft
        top_players = PlayerCRUD.get_top_players(db, scoring_type, limit=max(50, team_count * 4))
        if not top_players:
            raise HTTPException(status_code=400, detail="No players found. Ingest or scrape players first.")

        # Create league
        from ..data.models import League
        league = League(
            name="Demo League",
            league_size=team_count,
            scoring_type=scoring_type,
            roster_size=16,
            starting_lineup={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "DEF": 1},
            snake_draft=True,
        )
        db.add(league)
        db.commit()
        db.refresh(league)

        # Create teams
        teams = []
        for i in range(1, team_count + 1):
            team = Team(name=f"Team {i}", league_id=league.id, draft_position=i)
            db.add(team)
            teams.append(team)
        db.commit()
        for t in teams:
            db.refresh(t)

        # Create draft
        draft_order = [t.id for t in sorted(teams, key=lambda x: x.draft_position)]
        # Create draft row with only columns that exist in current DB schema
        inspector = sa_inspect(db.get_bind())
        draft_cols = {c['name'] for c in inspector.get_columns('drafts')}
        col_values = {
            "league_id": league.id,
            "status": "in_progress",
            "current_pick": 1,
            "current_round": 1,
            "draft_date": None,
            "completed_at": None,
        }
        # Optional columns if present
        if 'draft_order' in draft_cols:
            col_values['draft_order'] = draft_order
        if 'current_pick_index' in draft_cols:
            col_values['current_pick_index'] = 0
        if 'snake' in draft_cols:
            col_values['snake'] = True
        if 'scoring_mode' in draft_cols:
            col_values['scoring_mode'] = scoring_type
        if 'num_teams' in draft_cols:
            col_values['num_teams'] = team_count
        if 'draft_spot' in draft_cols:
            col_values['draft_spot'] = 1

        cols_sql = ', '.join(col_values.keys())
        params_sql = ', '.join(f":{k}" for k in col_values.keys())
        sql = text(f"INSERT INTO drafts ({cols_sql}) VALUES ({params_sql}) RETURNING id")
        result = db.execute(sql, col_values)
        draft_id_row = result.fetchone()
        db.commit()
        draft_id = draft_id_row[0]

        # Seed first two rounds of picks using top players by ADP
        total_seed_picks = min(len(top_players), team_count * 2)
        for i in range(total_seed_picks):
            round_num = (i // team_count) + 1
            pick_in_round = (i % team_count) + 1
            # Snake order handling for round 2
            if round_num % 2 == 0:
                team_index = team_count - pick_in_round
            else:
                team_index = pick_in_round - 1
            team_id = draft_order[team_index]

            player = top_players[i]
            DraftCRUD.create_draft_pick(db, {
                "draft_id": draft_id,
                "team_id": team_id,
                "player_id": player.id,
                "pick_number": i + 1,
                "round_number": round_num,
                "pick_in_round": pick_in_round,
            })

        return {"message": "Seeded sample league", "league_id": league.id, "team_count": team_count}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/simulate-bot-draft")
async def simulate_bot_draft(
    league_id: Optional[int] = None,
    team_count: int = 12,
    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR,
    main_team_position: int = 1,
    db: Session = Depends(get_db)
):
    """Create or use a league and simulate the ENTIRE snake draft with bot picks, persisted to DB."""
    try:
        # Ensure we have a player pool
        rounds_total = 16
        player_pool = PlayerCRUD.get_top_players(db, scoring_type, limit=max(300, team_count * rounds_total))
        if not player_pool:
            raise HTTPException(status_code=400, detail="No players found. Ingest players first.")

        # Create or fetch league
        from ..data.models import League, PositionEnum
        if league_id:
            league = db.query(League).filter(League.id == league_id).first()
            if not league:
                raise HTTPException(status_code=404, detail="League not found")
        else:
            league = League(
                name="Bot Draft League",
                league_size=team_count,
                scoring_type=scoring_type,
                roster_size=16,
                starting_lineup={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "DEF": 1},
                snake_draft=True,
            )
            db.add(league)
            db.commit()
            db.refresh(league)

        # Ensure teams exist
        teams = TeamCRUD.get_teams_by_league(db, league.id)
        if not teams:
            for i in range(1, team_count + 1):
                display_name = "User Draft Team" if i == main_team_position else f"Bot Team {i}"
                owner = "Main Bot" if i == main_team_position else None
                db.add(Team(name=display_name, owner_name=owner, league_id=league.id, draft_position=i))
            db.commit()
            teams = TeamCRUD.get_teams_by_league(db, league.id)

        if len(teams) < team_count:
            # Pad with more teams if needed
            current = len(teams)
            for i in range(current + 1, team_count + 1):
                display_name = "User Draft Team" if i == main_team_position else f"Bot Team {i}"
                owner = "Main Bot" if i == main_team_position else None
                db.add(Team(name=display_name, owner_name=owner, league_id=league.id, draft_position=i))
            db.commit()
            teams = TeamCRUD.get_teams_by_league(db, league.id)

        # Create draft
        # Normalize team labels to ensure exactly one main-user perspective team
        sorted_teams = sorted(teams, key=lambda x: x.draft_position)[:team_count]
        for t in sorted_teams:
            if t.draft_position == main_team_position:
                t.name = "User Draft Team"
                t.owner_name = "Main Bot"
        db.commit()

        draft_order = [t.id for t in sorted_teams]
        inspector = sa_inspect(db.get_bind())
        draft_cols = {c['name'] for c in inspector.get_columns('drafts')}
        col_values = {
            "league_id": league.id,
            "status": "in_progress",
            "current_pick": 1,
            "current_round": 1,
            "draft_date": None,
            "completed_at": None,
        }
        if 'draft_order' in draft_cols:
            col_values['draft_order'] = draft_order
        if 'current_pick_index' in draft_cols:
            col_values['current_pick_index'] = 0
        if 'snake' in draft_cols:
            col_values['snake'] = True
        if 'scoring_mode' in draft_cols:
            col_values['scoring_mode'] = scoring_type
        if 'num_teams' in draft_cols:
            col_values['num_teams'] = team_count
        if 'draft_spot' in draft_cols:
            col_values['draft_spot'] = 1

        cols_sql = ', '.join(col_values.keys())
        params_sql = ', '.join(f":{k}" for k in col_values.keys())
        sql = text(f"INSERT INTO drafts ({cols_sql}) VALUES ({params_sql}) RETURNING id")
        result = db.execute(sql, col_values)
        draft_id_row = result.fetchone()
        db.commit()
        draft_id = draft_id_row[0]

        # Helper: get ADP
        def get_adp(p):
            return getattr(p, f"adp_{scoring_type.value}", None) or 999

        # Roster needs per team
        starter_requirements = {PositionEnum.QB: 1, PositionEnum.RB: 2, PositionEnum.WR: 2, PositionEnum.TE: 1}
        bench_flex_buffer = 1  # One flex will be filled after starters
        roster_counts = {team_id: {pos: 0 for pos in PositionEnum} for team_id in draft_order}

        remaining_ids = {p.id for p in player_pool}
        id_to_player = {p.id: p for p in player_pool}
        sorted_pool_ids = [p.id for p in sorted(player_pool, key=lambda x: (get_adp(x), -(x.projected_points or 0)))]

        total_picks = min(len(sorted_pool_ids), team_count * rounds_total)
        for i in range(total_picks):
            round_num = (i // team_count) + 1
            pick_in_round = (i % team_count) + 1
            # Snake order
            idx = team_count - pick_in_round if (round_num % 2 == 0) else (pick_in_round - 1)
            picking_team_id = draft_order[idx]

            # Choose best available honoring starter needs first
            chosen_id = None
            # Try to satisfy remaining starters including FLEX (RB/WR/TE)
            need_positions = []
            counts = roster_counts[picking_team_id]
            for pos in [PositionEnum.RB, PositionEnum.WR, PositionEnum.TE, PositionEnum.QB]:
                required = starter_requirements.get(pos, 0)
                if counts[pos] < required:
                    need_positions.append(pos)

            # Determine if FLEX still unfilled from starters perspective
            rb_wr_te_have = counts[PositionEnum.RB] + counts[PositionEnum.WR] + counts[PositionEnum.TE]
            rb_wr_te_required_total = starter_requirements[PositionEnum.RB] + starter_requirements[PositionEnum.WR] + starter_requirements[PositionEnum.TE] + bench_flex_buffer
            flex_needed = rb_wr_te_have < rb_wr_te_required_total

            def can_fill(pos):
                if pos == PositionEnum.QB:
                    return counts[pos] < starter_requirements[pos]
                if pos in (PositionEnum.RB, PositionEnum.WR, PositionEnum.TE):
                    # allow until starters + flex satisfied
                    return flex_needed or counts[pos] < starter_requirements[pos]
                # Allow K/DEF later; deprioritize until late rounds
                return round_num >= rounds_total - 3

            # Pass 1: take best player that fills a need
            for pid in sorted_pool_ids:
                if pid not in remaining_ids:
                    continue
                p = id_to_player[pid]
                if can_fill(p.position):
                    chosen_id = pid
                    break

            # Pass 2: best available
            if chosen_id is None:
                for pid in sorted_pool_ids:
                    if pid in remaining_ids:
                        chosen_id = pid
                        break

            if chosen_id is None:
                break

            player = id_to_player[chosen_id]
            DraftCRUD.create_draft_pick(db, {
                "draft_id": draft_id,
                "team_id": picking_team_id,
                "player_id": player.id,
                "pick_number": i + 1,
                "round_number": round_num,
                "pick_in_round": pick_in_round,
            })

            remaining_ids.remove(chosen_id)
            roster_counts[picking_team_id][player.position] += 1

        # Mark draft complete
        # Update draft status if those columns exist
        try:
            status_sql = []
            params = {"id": draft_id}
            status_sql.append("status = :status")
            params['status'] = 'completed'
            inspector = sa_inspect(db.get_bind())
            draft_cols2 = {c['name'] for c in inspector.get_columns('drafts')}
            if 'current_pick' in draft_cols2:
                status_sql.append("current_pick = :cp")
                params['cp'] = min(total_picks + 1, team_count * rounds_total)
            if 'current_round' in draft_cols2:
                status_sql.append("current_round = :cr")
                params['cr'] = min(rounds_total, (params['cp'] - 1) // team_count + 1)
            if 'current_pick_index' in draft_cols2:
                status_sql.append("current_pick_index = :cpi")
                params['cpi'] = total_picks
            if status_sql:
                upd = text(f"UPDATE drafts SET {', '.join(status_sql)} WHERE id = :id")
                db.execute(upd, params)
                db.commit()
        except Exception:
            pass

        # Evaluate and store analysis so it appears in team analysis immediately
        evaluator = TeamEvaluator(db)
        main_team_id = next((t.id for t in sorted_teams if t.draft_position == main_team_position), sorted_teams[0].id)
        main_evaluation = evaluator.evaluate_team(main_team_id, scoring_type)

        # Optionally evaluate all teams to populate metrics
        for t in sorted_teams:
            try:
                evaluator.evaluate_team(t.id, scoring_type)
            except Exception:
                continue

        return {
            "message": "Simulated bot draft",
            "league_id": league.id,
            "draft_id": draft_id,
            "picks": total_picks,
            "main_team_id": main_team_id,
            "main_team_evaluation": main_evaluation,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/league-comparison/{league_id}")
async def compare_league_teams(
    league_id: int,
    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR,
    db: Session = Depends(get_db)
):
    """
    Compare all teams in a league with power rankings
    """
    try:
        evaluator = TeamEvaluator(db)
        comparison = evaluator.compare_teams(league_id, scoring_type)
        
        return comparison
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/scarcity-analysis")
async def get_scarcity_analysis(
    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR,
    position: Optional[PositionEnum] = None,
    db: Session = Depends(get_db)
):
    """
    Get positional scarcity analysis
    """
    try:
        if position:
            # Get specific position analysis
            analysis = ScarcityCRUD.get_scarcity_analysis(db, position, scoring_type)
            if not analysis:
                raise HTTPException(status_code=404, detail=f"No scarcity analysis found for {position}")
            
            return {
                "position": analysis.position.value,
                "scoring_type": analysis.scoring_type.value,
                "tier_breaks": analysis.tier_breaks,
                "drop_off_points": analysis.drop_off_points,
                "scarcity_score": analysis.scarcity_score,
                "player_count": analysis.player_count,
                "analysis_date": analysis.analysis_date.isoformat()
            }
        else:
            # Get all positions
            analyses = ScarcityCRUD.get_all_scarcity_analyses(db, scoring_type)
            
            return {
                "scoring_type": scoring_type.value,
                "positions": [
                    {
                        "position": analysis.position.value,
                        "tier_breaks": analysis.tier_breaks,
                        "drop_off_points": analysis.drop_off_points,
                        "scarcity_score": analysis.scarcity_score,
                        "player_count": analysis.player_count
                    }
                    for analysis in analyses
                ],
                "position_rankings": sorted(
                    [(a.position.value, a.scarcity_score) for a in analyses],
                    key=lambda x: x[1],
                    reverse=True
                )
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/team/{team_id}/details")
async def get_team_details(
    team_id: int,
    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR,
    db: Session = Depends(get_db)
):
    """Get team overview with latest draft context and evaluation"""
    team = TeamCRUD.get_team(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Latest draft in this team's league
    latest_draft_id = team.league.drafts[-1].id if team.league and team.league.drafts else None

    evaluator = TeamEvaluator(db)
    evaluation = evaluator.evaluate_team(team_id, scoring_type)

    # Team picks in latest draft
    team_picks = []
    if latest_draft_id:
        picks = DraftCRUD.get_team_picks(db, latest_draft_id, team_id)
        for p in picks:
            player = p.player
            team_picks.append({
                "pick_number": p.pick_number,
                "round_number": p.round_number,
                "pick_in_round": p.pick_in_round,
                "player": {
                    "id": player.id if player else None,
                    "name": player.name if player else None,
                    "position": player.position.value if player and player.position else None,
                    "team": player.team if player else None
                }
            })

    return {
        "team": {
            "id": team.id,
            "name": team.name,
            "league_id": team.league_id
        },
        "latest_draft_id": latest_draft_id,
        "evaluation": evaluation,
        "picks": team_picks
    }

@router.get("/team/{team_id}/draft-board")
async def get_team_draft_board(
    team_id: int,
    db: Session = Depends(get_db)
):
    """Get latest draft board for the team's league (all picks)"""
    team = TeamCRUD.get_team(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    if not team.league or not team.league.drafts:
        return {"message": "No draft available", "picks": []}

    latest_draft = team.league.drafts[-1]
    picks = DraftCRUD.get_draft_picks(db, latest_draft.id)

    board = []
    for p in picks:
        player = p.player
        board.append({
            "pick_number": p.pick_number,
            "round_number": p.round_number,
            "pick_in_round": p.pick_in_round,
            "team_id": p.team_id,
            "team_name": next((t.name for t in team.league.teams if t.id == p.team_id), f"Team {p.team_id}"),
            "player": {
                "id": player.id if player else None,
                "name": player.name if player else None,
                "position": player.position.value if player and player.position else None,
                "team": player.team if player else None
            }
        })

    return {
        "league_id": team.league_id,
        "draft_id": latest_draft.id,
        "current_pick": latest_draft.current_pick,
        "current_round": latest_draft.current_round,
        "picks": board
    }

@router.get("/team/{team_id}/simulation-preview")
async def get_team_simulation_preview(
    team_id: int,
    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR,
    db: Session = Depends(get_db)
):
    """Get a quick simulation preview (weekly score distribution) for a team"""
    team = TeamCRUD.get_team(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    simulator = SeasonSimulator(db)
    # Generate weekly scores using internal method to stay consistent with season simulation
    weekly_scores = simulator._generate_team_weekly_scores(team, scoring_type)

    return {
        "team_id": team.id,
        "team_name": team.name,
        "scoring_type": scoring_type.value,
        "weekly_scores": weekly_scores,
        "avg_score": round(sum(weekly_scores) / len(weekly_scores), 2)
    }

@router.post("/season-simulation/{league_id}")
async def simulate_season(
    league_id: int,
    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR,
    db: Session = Depends(get_db)
):
    """
    Run Monte Carlo season simulation for playoff probabilities
    """
    try:
        simulator = SeasonSimulator(db)
        results = simulator.simulate_season(league_id, scoring_type)
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/competitive-advantage/{team_id}")
async def get_competitive_advantage(
    team_id: int,
    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR,
    db: Session = Depends(get_db)
):
    """
    Get detailed competitive advantage analysis for a team
    """
    try:
        evaluator = TeamEvaluator(db)
        evaluation = evaluator.evaluate_team(team_id, scoring_type)
        
        # Enhanced analysis with competitive insights
        competitive_analysis = {
            "team_evaluation": evaluation,
            "strengths": [],
            "weaknesses": [],
            "recommendations": []
        }
        
        # Analyze strengths
        vorp_analysis = evaluation["vorp_analysis"]
        if vorp_analysis["starting_lineup_vorp"] > 20:
            competitive_analysis["strengths"].append("Elite starting lineup value")
        
        depth_analysis = evaluation["depth_analysis"]
        if depth_analysis["overall_depth_score"] > 6:
            competitive_analysis["strengths"].append("Strong roster depth")
        
        # Analyze weaknesses
        if vorp_analysis["starting_lineup_vorp"] < 0:
            competitive_analysis["weaknesses"].append("Below-average starting lineup")
        
        if depth_analysis["overall_depth_score"] < 4:
            competitive_analysis["weaknesses"].append("Lack of roster depth")
        
        bye_analysis = evaluation["bye_week_analysis"]
        if bye_analysis["total_bye_impact"] > 15:
            competitive_analysis["weaknesses"].append("Challenging bye week schedule")
        
        # Generate recommendations
        positional_strength = evaluation["positional_strength"]
        weak_positions = [pos for pos, data in positional_strength.items() 
                         if data.get("strength_grade", "C") in ["C", "D"]]
        
        if weak_positions:
            competitive_analysis["recommendations"].append(
                f"Consider upgrading at: {', '.join(weak_positions)}"
            )
        
        if depth_analysis["overall_depth_score"] < 5:
            competitive_analysis["recommendations"].append(
                "Focus on adding depth players from waiver wire"
            )
        
        return competitive_analysis
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/refresh-analysis")
async def refresh_analysis(
    scoring_type: ScoringTypeEnum = ScoringTypeEnum.PPR,
    db: Session = Depends(get_db)
):
    """
    Refresh scarcity analysis for all positions
    """
    try:
        analyzer = ScarcityAnalyzer(db)
        results = analyzer.analyze_all_positions(scoring_type)
        
        return {
            "message": "Analysis refreshed successfully",
            "scoring_type": scoring_type.value,
            "positions_analyzed": len(results),
            "results": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
